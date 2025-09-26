from types import SimpleNamespace

import pytest

from backend.services.alert_service import AlertService


class DummyAlert(SimpleNamespace):
    pass


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_alert_service_triggers_notification(monkeypatch):
    alert = DummyAlert(id=1, asset="AAPL", condition=">", value=100.0)

    service = AlertService(session_factory=None)
    service._session_factory = object()  # type: ignore[assignment]
    service._fetch_alerts = lambda: [alert]  # type: ignore[assignment]

    async def fake_price(symbol: str) -> float:
        return 105.0

    notified: list[tuple[DummyAlert, float]] = []

    async def fake_notify(alert_obj, price):  # noqa: ANN001
        notified.append((alert_obj, price))

    service._resolve_price = fake_price  # type: ignore[assignment]
    service._notify = fake_notify  # type: ignore[assignment]

    await service.evaluate_alerts()

    assert notified == [(alert, 105.0)]


def test_alert_service_should_trigger_conditions():
    service = AlertService(session_factory=None)

    alert_above = DummyAlert(condition=">", value=10.0)
    alert_below = DummyAlert(condition="<", value=10.0)
    alert_equal = DummyAlert(condition="==", value=10.0)

    assert service._should_trigger(alert_above, 10.0) is True
    assert service._should_trigger(alert_below, 9.5) is True
    assert service._should_trigger(alert_equal, 10.0000001) is True
    assert service._should_trigger(alert_equal, 10.1) is False


@pytest.mark.anyio
async def test_send_external_alert(monkeypatch):
    service = AlertService(session_factory=None)
    service._session_factory = object()  # type: ignore[assignment]
    service._telegram_token = "telegram-token"
    service._discord_token = "discord-token"
    service._discord_application_id = "discord-app"

    async def fake_telegram(chat_id: str, message: str) -> None:  # noqa: ANN001
        assert chat_id == "123"
        assert "Manual alert" in message

    async def fake_discord(channel_id: str, message: str) -> None:  # noqa: ANN001
        assert channel_id == "456"
        assert "Manual alert" in message

    monkeypatch.setattr(service, "_send_telegram_message", fake_telegram)
    monkeypatch.setattr(service, "_send_discord_message", fake_discord)

    result = await service.send_external_alert(
        message="Manual alert", telegram_chat_id="123", discord_channel_id="456"
    )

    assert result["telegram"]["status"] == "sent"
    assert result["discord"]["status"] == "sent"


@pytest.mark.anyio
async def test_send_external_alert_requires_target(monkeypatch):
    service = AlertService(session_factory=None)
    service._telegram_token = "telegram-token"

    with pytest.raises(ValueError):
        await service.send_external_alert(message="Hello")
