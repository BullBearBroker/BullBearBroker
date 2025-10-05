from __future__ import annotations

import importlib
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

ai_service_module = importlib.import_module("backend.services.ai_service")
alert_service_module = importlib.import_module("backend.services.alert_service")
from backend.services.ai_service import AIService
from backend.services.alert_service import AlertService
from backend.services.notification_dispatcher import NotificationDispatcher


class CounterStub:
    def __init__(self) -> None:
        self.count = 0

    def inc(self) -> None:
        self.count += 1


def _create_ai_service(
    monkeypatch: pytest.MonkeyPatch,
    counter: CounterStub,
    *,
    dispatcher_override: NotificationDispatcher | None = None,
):
    service = AIService()

    if dispatcher_override is None:
        broadcast_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(
            ai_service_module.notification_dispatcher,
            "broadcast_event",
            broadcast_mock,
            raising=False,
        )
    else:
        monkeypatch.setattr(
            ai_service_module,
            "notification_dispatcher",
            dispatcher_override,
            raising=False,
        )
        monkeypatch.setattr(
            "backend.services.notification_dispatcher.notification_dispatcher",
            dispatcher_override,
            raising=False,
        )
        broadcast_mock = None

    monkeypatch.setattr(
        ai_service_module, "ai_notifications_total", counter, raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False
    )

    def _analyze(self, _: str) -> dict[str, object]:
        return {
            "symbols": [],
            "interval": None,
            "use_market_data": False,
            "need_indicators": False,
            "need_news": False,
            "need_alerts": False,
            "forex_pairs": [],
        }

    async def _call_with_backoff(self, *_: object, **__: object) -> tuple[str, str]:
        return ("Insight generada", "mistral")

    service._analyze_message = MethodType(_analyze, service)
    service._build_prompt = MethodType(lambda self, *_: None, service)
    service._call_with_backoff = MethodType(_call_with_backoff, service)

    return service, broadcast_mock


def _create_alert_service(
    monkeypatch: pytest.MonkeyPatch,
    counter: CounterStub,
    *,
    dispatcher_override: NotificationDispatcher | None = None,
):
    service = AlertService(telegram_bot_token="token-fake")

    if dispatcher_override is None:
        broadcast_mock: AsyncMock = AsyncMock()
        monkeypatch.setattr(
            alert_service_module.notification_dispatcher,
            "broadcast_event",
            broadcast_mock,
            raising=False,
        )
    else:
        monkeypatch.setattr(
            alert_service_module,
            "notification_dispatcher",
            dispatcher_override,
            raising=False,
        )
        monkeypatch.setattr(
            "backend.services.notification_dispatcher.notification_dispatcher",
            dispatcher_override,
            raising=False,
        )
        broadcast_mock = None

    monkeypatch.setattr(
        alert_service_module, "alert_notifications_total", counter, raising=False
    )

    async def _send_telegram_message(self, *_: object, **__: object) -> None:
        return None

    async def _send_discord_message(self, *_: object, **__: object) -> None:
        return None

    service._send_telegram_message = MethodType(_send_telegram_message, service)
    service._send_discord_message = MethodType(_send_discord_message, service)

    async def _notify_telegram(self, *_: object, **__: object) -> None:
        return None

    service._notify_telegram = MethodType(_notify_telegram, service)

    return service, broadcast_mock


@pytest.mark.asyncio
async def test_broadcast_event_sends_to_all_channels() -> None:
    realtime = SimpleNamespace(broadcast=AsyncMock())
    push = SimpleNamespace(broadcast=AsyncMock(return_value=1))
    audit = MagicMock()
    dispatcher = NotificationDispatcher(realtime, push, audit)

    payload = {"text": "Hola"}
    await dispatcher.broadcast_event("ai_insight", payload)

    realtime.broadcast.assert_awaited_once()
    push.broadcast.assert_awaited_once()
    audit.log_event.assert_called_once_with(
        None, "notification_sent", {"type": "ai_insight", "size": len(str(payload))}
    )

    realtime_args = realtime.broadcast.await_args
    assert realtime_args.args[0]["type"] == "ai_insight"
    assert realtime_args.args[0]["payload"] == payload


@pytest.mark.asyncio
async def test_ai_service_triggers_broadcast_on_insight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = CounterStub()
    service, broadcast_mock = _create_ai_service(monkeypatch, counter)

    response = await service.process_message("Genera insight")

    assert response.text
    assert broadcast_mock is not None
    assert broadcast_mock.await_count == 1
    broadcast_mock.assert_awaited_once()
    call_args = broadcast_mock.await_args
    assert call_args.args[0] == "ai_insight"
    assert call_args.args[1]["source"] == "ai"
    assert counter.count == 1


@pytest.mark.asyncio
async def test_alert_service_triggers_broadcast_on_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = CounterStub()
    service, broadcast_mock = _create_alert_service(monkeypatch, counter)

    result = await service.send_external_alert(
        message="Precio en alza", telegram_chat_id="123"
    )

    assert "telegram" in result
    assert broadcast_mock is not None
    broadcast_mock.assert_awaited_once()
    args = broadcast_mock.await_args
    assert args.args[0] == "alert"
    assert counter.count == 1


@pytest.mark.asyncio
async def test_broadcast_logs_and_metrics_increment(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    realtime = SimpleNamespace(broadcast=AsyncMock())
    push = SimpleNamespace(broadcast=AsyncMock(return_value=2))
    audit = MagicMock()
    dispatcher = NotificationDispatcher(realtime, push, audit)

    ai_counter = CounterStub()
    alert_counter = CounterStub()

    service, _ = _create_ai_service(
        monkeypatch, ai_counter, dispatcher_override=dispatcher
    )
    alert_service, _ = _create_alert_service(
        monkeypatch, alert_counter, dispatcher_override=dispatcher
    )

    caplog.set_level("INFO")

    await service.process_message("Insight rapido")
    await alert_service.send_external_alert(
        message="Caída del mercado", telegram_chat_id="321"
    )
    dummy_alert = SimpleNamespace(
        asset="AAPL",
        value=101.5,
        condition=">",
        title="AAPL alerta",
    )
    await alert_service._notify(dummy_alert, 102.3)
    await dispatcher.broadcast_event("manual", {"text": "ping"})

    assert ai_counter.count == 1
    assert alert_counter.count == 2  # incluye alerta interna y externa

    messages = [
        record.message
        for record in caplog.records
        if "notification_dispatcher" in record.message
    ]
    assert any("broadcast_complete" in message for message in messages)

    audit.log_event.assert_called()
