"""Servicio encargado de evaluar y notificar alertas de precios."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Tuple

# APScheduler es opcional en entornos de prueba donde no se pueda instalar.
try:  # pragma: no cover - la importación depende del entorno
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
except Exception:  # pragma: no cover - sin APScheduler disponible
    AsyncIOScheduler = None  # type: ignore[assignment]
    IntervalTrigger = None  # type: ignore[assignment]
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

try:  # pragma: no cover - compatibilidad con distintos puntos de entrada
    from ..models import Alert
    from ..utils.config import Config
except ImportError:  # pragma: no cover - ejecución directa desde backend/
    from models import Alert  # type: ignore[no-redef]
    from utils.config import Config  # type: ignore[no-redef]

from .forex_service import forex_service
from .market_service import market_service

try:  # pragma: no cover - telemetría opcional
    from telegram import Bot
except Exception:  # pragma: no cover - PTB opcional
    Bot = None

try:
    from services.user_service import SessionLocal as DefaultSessionLocal
except Exception:  # pragma: no cover - puede no estar configurado en tests
    DefaultSessionLocal = None


LOGGER = logging.getLogger(__name__)


class AlertService:
    """Administra alertas periódicas empleando APScheduler."""

    def __init__(
        self,
        *,
        session_factory: Optional[sessionmaker] = DefaultSessionLocal,
        scheduler: Optional[AsyncIOScheduler] = None,
        interval_seconds: int = 60,
        telegram_bot_token: Optional[str] = Config.TELEGRAM_BOT_TOKEN,
    ) -> None:
        self._session_factory = session_factory
        if scheduler is not None:
            self._scheduler = scheduler
        elif AsyncIOScheduler is not None:
            self._scheduler = AsyncIOScheduler()
        else:
            self._scheduler = None
        self._job = None
        self._interval = interval_seconds
        self._websocket_manager = None
        self.is_running = False
        self._telegram_bot = Bot(telegram_bot_token) if telegram_bot_token and Bot else None

    def register_websocket_manager(self, manager) -> None:
        """Permite enviar notificaciones en tiempo real mediante websockets."""

        self._websocket_manager = manager

    async def start(self) -> None:
        """Inicia el scheduler si hay base de datos disponible."""

        if self._session_factory is None:
            LOGGER.warning("AlertService: sin base de datos, se omite el scheduler")
            return
        if self._scheduler is None:
            LOGGER.warning("AlertService: APScheduler no disponible, las alertas se ejecutarán bajo demanda")
            return
        if not self._scheduler.running:
            self._scheduler.start()
        if self._job is None and IntervalTrigger is not None:
            trigger = IntervalTrigger(seconds=self._interval)
            self._job = self._scheduler.add_job(self.evaluate_alerts, trigger)
        self.is_running = True

    async def stop(self) -> None:
        if self._job is not None:
            self._job.remove()
            self._job = None
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self.is_running = False

    async def evaluate_alerts(self) -> None:
        """Consulta alertas activas y envía notificaciones cuando procede."""

        if self._session_factory is None:
            return

        alerts = await asyncio.to_thread(self._fetch_alerts)
        if not alerts:
            return

        triggered: List[Tuple[Alert, float]] = []
        for alert in alerts:
            price = await self._resolve_price(alert.asset)
            if price is None:
                continue
            if self._should_trigger(alert, price):
                triggered.append((alert, price))

        if not triggered:
            return

        for alert, price in triggered:
            await self._notify(alert, price)

    def _fetch_alerts(self) -> List[Alert]:
        assert self._session_factory is not None
        with self._session_factory() as session:
            result = session.scalars(select(Alert)).all()
            for alert in result:
                session.expunge(alert)
            return result

    async def _resolve_price(self, symbol: str) -> Optional[float]:
        stock = await market_service.get_stock_price(symbol)
        if stock and stock.get("price") is not None:
            return float(stock["price"])

        crypto = await market_service.get_crypto_price(symbol)
        if crypto and crypto.get("price") is not None:
            return float(crypto["price"])

        fx = await forex_service.get_quote(symbol)
        if fx and fx.get("price") is not None:
            return float(fx["price"])

        return None

    @staticmethod
    def _should_trigger(alert: Alert, price: float) -> bool:
        condition = alert.condition or ">"
        if condition in (">", "above"):
            return price >= alert.value
        if condition in ("<", "below"):
            return price <= alert.value
        if condition in ("==", "equal"):
            return abs(price - alert.value) <= 1e-6
        return False

    async def _notify(self, alert: Alert, price: float) -> None:
        message = (
            f"Alerta para {alert.asset}: precio actual {price:.2f}, objetivo {alert.value:.2f}"
        )
        payload = {
            "type": "alert",
            "symbol": alert.asset,
            "price": price,
            "target": alert.value,
            "comparison": alert.condition,
            "message": message,
        }
        if self._websocket_manager is not None:
            try:
                await self._websocket_manager.broadcast(payload)
            except Exception as exc:  # pragma: no cover - logging defensivo
                LOGGER.warning("AlertService: error notificando por WebSocket: %s", exc)

        await self._notify_telegram(alert, message)

    async def _notify_telegram(self, alert: Alert, message: str) -> None:
        if not self._telegram_bot:
            return
        chat_id = Config.TELEGRAM_DEFAULT_CHAT_ID
        if not chat_id:
            return
        try:
            await self._telegram_bot.send_message(chat_id=chat_id, text=message)
        except Exception as exc:  # pragma: no cover - no queremos fallar por notificaciones
            LOGGER.warning("AlertService: error enviando mensaje a Telegram: %s", exc)


alert_service = AlertService()


async def main() -> None:  # pragma: no cover - utilidad CLI
    await alert_service.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        await alert_service.stop()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
