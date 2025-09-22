from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

try:  # pragma: no cover - import opcional según entorno
    from apscheduler.jobstores.redis import RedisJobStore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    APSCHEDULER_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - fallback cuando no está instalado
    RedisJobStore = None  # type: ignore[assignment]
    AsyncIOScheduler = None  # type: ignore[assignment]
    IntervalTrigger = None  # type: ignore[assignment]
    APSCHEDULER_AVAILABLE = False

from models import Alert
from services.market_service import market_service
from services.user_service import user_service
from utils.config import Config

logger = logging.getLogger(__name__)


class AlertNotificationManager:
    """Gestiona suscriptores WebSocket para notificaciones de alertas."""

    def __init__(self) -> None:
        self._connections: List[Any] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        await websocket.send_json(
            {
                "type": "alerts_connection_established",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def disconnect(self, websocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections)
        for connection in connections:
            try:
                await connection.send_json(payload)
            except Exception:
                await self.disconnect(connection)


def _build_redis_jobstore(redis_url: str) -> RedisJobStore:
    if not APSCHEDULER_AVAILABLE or RedisJobStore is None:  # pragma: no cover - entorno sin APScheduler
        raise RuntimeError("APScheduler no disponible en el entorno actual")
    parsed = urlparse(redis_url)
    db = 0
    if parsed.path and len(parsed.path) > 1:
        try:
            db = int(parsed.path.lstrip("/"))
        except ValueError:
            db = 0
    kwargs: Dict[str, Any] = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "db": db,
    }
    if parsed.password:
        kwargs["password"] = parsed.password
    if parsed.username:
        kwargs["username"] = parsed.username
    if parsed.scheme == "rediss":
        kwargs["ssl"] = True
    return RedisJobStore(**kwargs)


class AlertService:
    """Programa la evaluación de alertas usando APScheduler con backend Redis."""

    def __init__(self, notification_manager: AlertNotificationManager) -> None:
        self.notification_manager = notification_manager
        self._redis_url = Config.REDIS_URL
        self._evaluation_interval = Config.ALERT_EVALUATION_INTERVAL
        self._scheduler_available = APSCHEDULER_AVAILABLE and AsyncIOScheduler is not None
        self._scheduler = (
            AsyncIOScheduler(
                jobstores={"default": _build_redis_jobstore(self._redis_url)}, timezone="UTC"
            )
            if self._scheduler_available
            else None
        )
        self._job_id = "alerts.evaluate"
        self._telegram_token = Config.TELEGRAM_BOT_TOKEN
        self._telegram_chat_id = Config.TELEGRAM_CHAT_ID
        self._timeout = aiohttp.ClientTimeout(total=15)
        self._background_task: Optional[asyncio.Task] = None
        self._fallback_running = False

    def start_scheduler(self) -> None:
        if self._scheduler_available and self._scheduler:
            if not self._scheduler.running:
                logger.info("Iniciando scheduler de alertas con backend Redis")
                self._scheduler.start()
            if not self._scheduler.get_job(self._job_id):
                self._scheduler.add_job(
                    self._schedule_runner,
                    trigger=IntervalTrigger(seconds=self._evaluation_interval),
                    id=self._job_id,
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )
        else:
            if not self._fallback_running:
                logger.warning(
                    "APScheduler no disponible, activando planificador asíncrono básico"
                )
                self._fallback_running = True
                loop = asyncio.get_running_loop()
                self._background_task = loop.create_task(self._fallback_scheduler())

    async def shutdown(self) -> None:
        if self._scheduler_available and self._scheduler and self._scheduler.running:
            logger.info("Deteniendo scheduler de alertas")
            self._scheduler.shutdown(wait=False)
        if self._background_task:
            self._fallback_running = False
            self._background_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._background_task
            self._background_task = None

    def _schedule_runner(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        loop.create_task(self.evaluate_alerts())

    async def _fallback_scheduler(self) -> None:
        try:
            while self._fallback_running:
                await self.evaluate_alerts()
                await asyncio.sleep(self._evaluation_interval)
        except asyncio.CancelledError:  # pragma: no cover - cancelación controlada
            pass

    async def evaluate_alerts(self) -> None:
        alerts = await asyncio.to_thread(user_service.get_all_active_alerts)
        if not alerts:
            return
        for alert in alerts:
            try:
                await self._evaluate_single_alert(alert)
            except Exception as exc:  # pragma: no cover - logging de resiliencia
                logger.exception("Error evaluando alerta %s: %s", alert.id, exc)

    async def _evaluate_single_alert(self, alert: Alert) -> None:
        asset_type = alert.asset_type or await market_service.detect_asset_type(alert.symbol)
        price_snapshot = await market_service.get_price(alert.symbol, asset_type)
        if not price_snapshot:
            return
        price = price_snapshot.get("raw_price")
        change = price_snapshot.get("raw_change")
        if price is None:
            return
        if not self._should_trigger(alert, price, change):
            return

        updated_alert = await asyncio.to_thread(
            user_service.mark_alert_triggered, alert.id, price, datetime.utcnow()
        )
        if not updated_alert:
            return
        payload = {
            "type": "alert_triggered",
            "alert": updated_alert.to_dict(),
            "price_snapshot": price_snapshot,
            "triggered_at": updated_alert.triggered_at.isoformat()
            if updated_alert.triggered_at
            else datetime.utcnow().isoformat(),
        }
        await self.notification_manager.broadcast(payload)
        await self._notify_telegram(updated_alert, price_snapshot)

    @staticmethod
    def _should_trigger(alert: Alert, price: float, change: Optional[float]) -> bool:
        condition = alert.condition_type.lower()
        threshold = alert.threshold_value
        if condition == "above":
            return price >= threshold
        if condition == "below":
            return price <= threshold
        if condition == "percent_change" and change is not None:
            return abs(change) >= threshold
        return False

    async def _notify_telegram(self, alert: Alert, price_snapshot: Dict[str, Any]) -> None:
        if not (self._telegram_token and self._telegram_chat_id):
            return
        message = (
            f"\U0001F514 Alerta para {alert.symbol}: {alert.condition_type} {alert.threshold_value}\n"
            f"Precio actual: {price_snapshot.get('price')}"
        )
        url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
        payload = {"chat_id": self._telegram_chat_id, "text": message}
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status >= 400:
                    logger.warning(
                        "Telegram notificó estado %s para la alerta %s", response.status, alert.id
                    )


alert_notification_manager = AlertNotificationManager()
alert_service = AlertService(notification_manager=alert_notification_manager)
