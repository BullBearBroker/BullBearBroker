"""Servicio encargado de evaluar y notificar alertas de precios."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Dict, List, Optional, Tuple

# APScheduler es opcional
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
except Exception:
    AsyncIOScheduler = None  # type: ignore[assignment]
    IntervalTrigger = None  # type: ignore[assignment]

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

try:
    from backend.models import Alert
    from backend.utils.config import Config
except ImportError:
    from backend.models import Alert  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]

from .forex_service import forex_service
from .market_service import market_service

try:
    import aiohttp
except Exception:  # pragma: no cover - aiohttp es dependencia opcional en runtime
    aiohttp = None  # type: ignore[assignment]

try:
    from telegram import Bot
except Exception:
    Bot = None

try:
    from backend.services.user_service import SessionLocal as DefaultSessionLocal
except Exception:
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
        self._telegram_token = telegram_bot_token or Config.TELEGRAM_BOT_TOKEN
        self._telegram_bot = (
            Bot(self._telegram_token) if self._telegram_token and Bot else None
        )
        self._discord_token = Config.DISCORD_BOT_TOKEN
        self._discord_application_id = Config.DISCORD_APPLICATION_ID

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
            except Exception as exc:
                LOGGER.warning("AlertService: error notificando por WebSocket: %s", exc)

        await self._notify_telegram(alert, message)

    async def _notify_telegram(self, alert: Alert, message: str) -> None:
        chat_id = Config.TELEGRAM_DEFAULT_CHAT_ID
        if not chat_id:
            return
        try:
            await self._send_telegram_message(chat_id, message)
        except Exception as exc:
            LOGGER.warning("AlertService: error enviando mensaje a Telegram: %s", exc)

    async def send_external_alert(
        self,
        *,
        message: str,
        telegram_chat_id: Optional[str] = None,
        discord_channel_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, str]]:
        """Send an arbitrary alert message through configured providers."""

        targets = []
        if telegram_chat_id:
            targets.append(("telegram", telegram_chat_id))
        if discord_channel_id:
            targets.append(("discord", discord_channel_id))

        if not targets:
            raise ValueError("No notification targets were provided")

        results: Dict[str, Dict[str, str]] = {}
        deliveries = []
        for provider, target in targets:
            if provider == "telegram":
                deliveries.append(
                    self._send_with_result(
                        provider,
                        target,
                        self._send_telegram_message(target, message),
                    )
                )
            elif provider == "discord":
                deliveries.append(
                    self._send_with_result(
                        provider,
                        target,
                        self._send_discord_message(target, message),
                    )
                )

        for provider, target, outcome in await asyncio.gather(*deliveries):
            results[provider] = {
                "target": target,
                "status": "sent" if outcome is None else "error",
                **({"error": outcome} if outcome else {}),
            }

        return results

    async def _send_with_result(
        self,
        provider: str,
        target: str,
        coroutine: Awaitable[None],
    ) -> Tuple[str, str, Optional[str]]:
        try:
            await coroutine
            return provider, target, None
        except Exception as exc:  # pragma: no cover - errors surfaced to caller
            LOGGER.error("AlertService: %s delivery failed: %s", provider, exc)
            return provider, target, str(exc)

    async def _send_telegram_message(self, chat_id: str, message: str) -> None:
        token = self._telegram_token
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN no configurado")

        if self._telegram_bot is not None:
            await self._telegram_bot.send_message(chat_id=chat_id, text=message)
            return

        if aiohttp is None:
            raise RuntimeError("aiohttp es requerido para enviar mensajes de Telegram")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(
                        f"Telegram API devolvió estado {response.status}: {body}"
                    )

    async def _send_discord_message(self, channel_id: str, message: str) -> None:
        if not self._discord_token:
            raise RuntimeError("DISCORD_BOT_TOKEN no configurado")
        if not self._discord_application_id:
            raise RuntimeError("DISCORD_APPLICATION_ID no configurado")
        if aiohttp is None:
            raise RuntimeError("aiohttp es requerido para enviar mensajes de Discord")

        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {self._discord_token}",
            "Content-Type": "application/json",
        }
        payload = {"content": message}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=10) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(
                        f"Discord API devolvió estado {response.status}: {body}"
                    )


alert_service = AlertService()


async def main() -> None:
    await alert_service.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        await alert_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
