from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.alert import Alert
from backend.models.base import Base
from backend.services.alert_service import AlertService


class DummyAlert(SimpleNamespace):
    pass


@pytest.fixture()
def in_memory_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


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


def test_fetch_alerts_returns_persisted_alert(in_memory_session_factory) -> None:
    service = AlertService(session_factory=in_memory_session_factory)
    user_id = uuid4()

    with in_memory_session_factory() as session:
        alert = Alert(
            user_id=user_id,
            title="Breakout",
            asset="AAPL",
            condition=">",
            value=150.0,
            active=True,
        )
        session.add(alert)
        session.commit()

    stored = service._fetch_alerts()
    assert len(stored) == 1
    assert stored[0].asset == "AAPL"
    assert stored[0].active is True


def test_validate_condition_expression_rejects_invalid_data() -> None:
    service = AlertService(session_factory=None)

    with pytest.raises(ValueError):
        service.validate_condition_expression("")
    with pytest.raises(ValueError):
        service.validate_condition_expression("RSI(14) + >")


def test_toggle_alert_active_state(in_memory_session_factory) -> None:
    service = AlertService(session_factory=in_memory_session_factory)
    user_id = uuid4()

    with in_memory_session_factory() as session:
        alert = Alert(
            user_id=user_id,
            title="Resistance",
            asset="TSLA",
            condition="<",
            value=200.0,
            active=True,
        )
        session.add(alert)
        session.commit()
        alert_id = alert.id

    assert [stored.id for stored in service._fetch_alerts()] == [alert_id]

    with in_memory_session_factory() as session:
        record = session.get(Alert, alert_id)
        assert record is not None
        record.active = False
        session.commit()

    assert service._fetch_alerts() == []

    with in_memory_session_factory() as session:
        record = session.get(Alert, alert_id)
        assert record is not None
        record.active = True
        session.commit()

    assert [stored.id for stored in service._fetch_alerts()] == [alert_id]


@pytest.mark.anyio
async def test_send_with_result_returns_error_details() -> None:
    service = AlertService(session_factory=None)

    async def failing_operation():
        raise RuntimeError("alert not found")

    provider, target, outcome = await service._send_with_result(
        "websocket",
        "missing",
        failing_operation(),
    )

    assert provider == "websocket"
    assert target == "missing"
    assert outcome == "alert not found"
