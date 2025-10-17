"""Servicio encargado de evaluar y notificar alertas de precios."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable
from typing import Any, NamedTuple

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

from backend.metrics.ai_metrics import alert_notifications_total
from backend.services import forex_service, market_service
from backend.services.ai_service import (  # ✅ fix import path (QA 2.0): corregimos namespace para ejecución en Docker
    ai_service,
)
from backend.services.notification_dispatcher import notification_dispatcher

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


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class AlertService:
    """Administra alertas periódicas empleando APScheduler."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker | None = DefaultSessionLocal,
        scheduler: AsyncIOScheduler | None = None,
        interval_seconds: int = 60,
        telegram_bot_token: str | None = Config.TELEGRAM_BOT_TOKEN,
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
        self.logger = LOGGER

    def register_websocket_manager(self, manager) -> None:
        """Permite enviar notificaciones en tiempo real mediante websockets."""
        self._websocket_manager = manager

    async def start(self) -> None:
        """Inicia el scheduler si hay base de datos disponible."""
        if self._session_factory is None:
            LOGGER.warning("AlertService: sin base de datos, se omite el scheduler")
            return
        if self._scheduler is None:
            LOGGER.warning(
                "AlertService: APScheduler no disponible, las alertas se ejecutarán bajo demanda"
            )
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

        triggered: list[tuple[Alert, float]] = []
        for alert in alerts:
            if not getattr(alert, "active", True):
                continue
            price = await self._resolve_price(alert.asset)
            if price is None:
                continue
            if self._should_trigger(alert, price):
                triggered.append((alert, price))

        if not triggered:
            return

        for alert, price in triggered:
            await self._notify(alert, price)

    def _fetch_alerts(self) -> list[Alert]:
        assert self._session_factory is not None
        with self._session_factory() as session:
            result = session.scalars(select(Alert).where(Alert.active.is_(True))).all()
            for alert in result:
                session.expunge(alert)
            return result

    async def _resolve_price(self, symbol: str) -> float | None:
        stock = await market_service.get_stock_price(symbol)
        price = _to_float_or_none(stock.get("price") if stock else None)
        if price is not None:
            return price

        crypto = await market_service.get_crypto_price(symbol)
        price = _to_float_or_none(crypto.get("price") if crypto else None)
        if price is not None:
            return price

        fx = await forex_service.get_quote(symbol)
        price = _to_float_or_none(fx.get("price") if fx else None)
        if price is not None:
            return price

        return None

    @staticmethod
    def _should_trigger(alert: Alert, price: float) -> bool:
        if not getattr(alert, "active", True):
            return False
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
            f"Alerta '{getattr(alert, 'title', alert.asset)}' para {alert.asset}: "
            f"precio actual {price:.2f}, objetivo {alert.value:.2f}"
        )
        payload = {
            "type": "alert",
            "symbol": alert.asset,
            "price": price,
            "target": alert.value,
            "comparison": alert.condition,
            "message": message,
        }
        try:
            await notification_dispatcher.broadcast_event(
                "alert",
                {
                    "title": getattr(alert, "title", alert.asset),
                    "price": price,
                    "target": alert.value,
                    "message": message,
                    "symbol": alert.asset,
                },
            )
            alert_notifications_total.inc()
        except Exception as exc:  # pragma: no cover - avoid breaking alert flow
            self.logger.warning(
                {
                    "service": "alert_service",
                    "event": "notification_dispatch_failed",
                    "error": str(exc),
                }
            )

        if self._websocket_manager is not None:
            try:
                await self._websocket_manager.broadcast(payload)
            except Exception as exc:
                LOGGER.warning("AlertService: error notificando por WebSocket: %s", exc)

        await self._notify_telegram(alert, message)

    async def suggest_alert_from_insight(
        self, symbol: str, insight: str, threshold: float = 0.05
    ):
        """
        Crea una alerta sugerida automáticamente basada en la información de un insight IA.
        """

        normalized = (insight or "").lower()
        if "compra" in normalized:
            condition = f"price_change > {threshold}"
        elif "venta" in normalized:
            condition = f"price_change < -{threshold}"
        else:
            condition = f"abs(price_change) > {threshold}"

        alert_data = {
            "symbol": symbol,
            "condition": condition,
            "active": True,
            "source": "ai_insight",
        }
        self.logger.info(
            json.dumps(
                {
                    "alert_event": "suggested_alert",
                    "symbol": symbol,
                    "condition": condition,
                }
            )
        )
        return alert_data

    async def _notify_telegram(self, alert: Alert, message: str) -> None:
        chat_id = Config.TELEGRAM_DEFAULT_CHAT_ID
        if not chat_id:
            return
        try:
            await self._send_telegram_message(chat_id, message)
        except Exception as exc:
            LOGGER.warning("AlertService: error enviando mensaje a Telegram: %s", exc)

    async def suggest_alert_condition(
        self, asset: str, interval: str = "1h"
    ) -> dict[str, str]:
        """Genera una condición sugerida usando IA para un activo dado."""  # [Codex] nuevo
        asset_clean = (asset or "").strip().upper()
        if not asset_clean:
            raise ValueError("Se requiere el símbolo del activo")

        interval_norm = (interval or "1h").lower()
        if interval_norm not in {"1h", "4h", "1d"}:
            interval_norm = "1h"

        prompt = (
            "Genera una recomendación breve para configurar una alerta automática "
            f"en el activo {asset_clean} con datos del intervalo {interval_norm}. "
            "Responde EXACTAMENTE en dos líneas usando el formato:\n"
            "Condición: <regla técnica concisa>\nNota: <explicación corta>."
            "Utiliza indicadores como RSI, MACD, ATR o VWAP según aplique."
        )

        try:
            ai_payload = await ai_service.process_message(prompt)
        except Exception as exc:
            LOGGER.warning(
                "No se pudo obtener sugerencia AI para %s: %s", asset_clean, exc
            )
            fallback = f"{asset_clean} precio cruza promedio de 20 velas"
            return {
                "suggestion": fallback,
                "notes": "Sugerencia local por indisponibilidad de IA",
            }

        # [Codex] cambiado - la IA ahora regresa metadatos, tomamos el texto plano
        ai_text = ai_payload.text if hasattr(ai_payload, "text") else str(ai_payload)

        condition = None
        note = None
        for raw_line in ai_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lower = line.lower()
            if lower.startswith("condición"):
                condition = line.split(":", 1)[-1].strip() if ":" in line else line
            elif lower.startswith("nota"):
                note = line.split(":", 1)[-1].strip() if ":" in line else line

        if not condition:
            condition = (
                ai_text.splitlines()[0].strip()
                if ai_text.strip()
                else "Condición no disponible"
            )
        if not note:
            note = "Generada automáticamente por IA"

        return {
            "suggestion": condition,
            "notes": note,
        }

    def validate_condition_expression(self, condition: str) -> None:
        """Validar sintaxis de la expresión de condición."""

        expression = (condition or "").strip()
        if not expression:
            raise ValueError("La condición de la alerta es obligatoria")

        legacy_comparators = {"<", ">", "=="}
        if expression in legacy_comparators:
            return

        parser = _ConditionExpressionParser(expression)
        parser.parse()

    async def send_external_alert(
        self,
        *,
        message: str,
        telegram_chat_id: str | None = None,
        discord_channel_id: str | None = None,
    ) -> dict[str, dict[str, str]]:
        """Send an arbitrary alert message through configured providers."""

        targets = []
        if telegram_chat_id:
            targets.append(("telegram", telegram_chat_id))
        if discord_channel_id:
            targets.append(("discord", discord_channel_id))

        if not targets:
            raise ValueError("No notification targets were provided")

        results: dict[str, dict[str, str]] = {}
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

        notification_targets = [target for _, target in targets]
        try:
            await notification_dispatcher.broadcast_event(
                "alert",
                {
                    "title": message.split(":", 1)[0] if ":" in message else message,
                    "message": message,
                    "targets": notification_targets,
                    "category": "alerts",
                },
            )
            alert_notifications_total.inc()
        except (
            Exception
        ) as exc:  # pragma: no cover - keep external alert reporting resilient
            self.logger.warning(
                {
                    "service": "alert_service",
                    "event": "external_notification_dispatch_failed",
                    "error": str(exc),
                }
            )

        return results

    async def _send_with_result(
        self,
        provider: str,
        target: str,
        coroutine: Awaitable[None],
    ) -> tuple[str, str, str | None]:
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
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=payload, timeout=10) as response,
        ):
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

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, json=payload, timeout=10) as response,
        ):
            if response.status >= 400:
                body = await response.text()
                raise RuntimeError(
                    f"Discord API devolvió estado {response.status}: {body}"
                )


class _ConditionExpressionParser:
    """Pequeño parser para validar expresiones condicionales de alertas."""

    _TOKEN_SPECIFICATION = [
        ("WS", r"\s+"),
        ("AND", r"AND\b"),
        ("OR", r"OR\b"),
        ("EQ", r"=="),
        ("LT", r"<"),
        ("GT", r">"),
        ("PLUS", r"\+"),
        ("MINUS", r"-"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("COMMA", r","),
        ("NUMBER", r"\d+(?:\.\d+)?"),
        ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ]

    _TOKEN_REGEX = re.compile(
        "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPECIFICATION),
        re.IGNORECASE,
    )

    def __init__(self, expression: str) -> None:
        self.expression = expression
        self.tokens = self._tokenize(expression)
        self.index = 0

    def parse(self) -> None:
        if not self.tokens:
            raise ValueError("La condición no puede estar vacía")
        self._parse_expression()
        if self._current() is not None:
            token = self._current()
            raise ValueError(f"Token inesperado '{token.value}' en la condición")

    # ---- Grammar helpers -------------------------------------------------
    def _parse_expression(self) -> None:
        self._parse_comparison()
        while True:
            if self._match("AND") or self._match("OR"):
                self._parse_comparison()
            else:
                break

    def _parse_comparison(self) -> None:
        self._parse_additive()
        if self._match("LT") or self._match("GT") or self._match("EQ"):
            self._parse_additive()
        else:
            raise ValueError("Se esperaba un operador de comparación (<, >, ==)")

    def _parse_additive(self) -> None:
        self._parse_factor()
        while True:
            if self._match("PLUS") or self._match("MINUS"):
                self._parse_factor()
            else:
                break

    def _parse_factor(self) -> None:
        if self._match("LPAREN"):
            self._parse_expression()
            self._expect("RPAREN", "Se esperaba ')' en la condición")
            return

        if self._match("NUMBER"):
            return

        token = self._match("IDENT")
        if token is None:
            raise ValueError(
                "Se esperaba un indicador, identificador o número en la condición"
            )

        # Funciones tipo RSI(14)
        if self._match("LPAREN"):
            if self._match("RPAREN"):
                return
            self._parse_function_arguments()
            self._expect("RPAREN", "Se esperaba ')' al cerrar la función")

    def _parse_function_arguments(self) -> None:
        while True:
            if not (self._match("NUMBER") or self._match("IDENT")):
                raise ValueError("Argumento de función inválido en la condición")
            if self._match("COMMA"):
                continue
            break

    # ---- Token utilities -------------------------------------------------
    def _tokenize(self, expression: str) -> list[_Token]:
        tokens: list[_Token] = []
        position = 0
        while position < len(expression):
            match = self._TOKEN_REGEX.match(expression, position)
            if not match:
                snippet = expression[position : position + 10]
                raise ValueError(f"Símbolo inesperado cerca de '{snippet}'")
            kind = match.lastgroup
            value = match.group()
            position = match.end()

            if kind == "WS":
                continue
            if kind in {"AND", "OR"}:
                tokens.append(_Token(kind.upper(), value.upper()))
            else:
                tokens.append(_Token(kind.upper(), value))
        return tokens

    def _current(self) -> _Token | None:
        if self.index < len(self.tokens):
            return self.tokens[self.index]
        return None

    def _match(self, token_type: str) -> _Token | None:
        current = self._current()
        if current and current.type == token_type:
            self.index += 1
            return current
        return None

    def _expect(self, token_type: str, message: str) -> None:
        if self._match(token_type) is None:
            raise ValueError(message)


class _Token(NamedTuple):
    type: str
    value: str


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
