from datetime import datetime, timedelta
from importlib import import_module
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.alert import Alert
from backend.models.base import Base

alert_service_module = import_module("backend.services.alert_service")
from backend.services.alert_service import AlertService  # noqa: E402


@pytest.fixture()
def in_memory_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def service(in_memory_factory) -> AlertService:
    return AlertService(session_factory=in_memory_factory)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_suggest_alert_condition_rejects_incomplete_payload(
    service: AlertService,
) -> None:
    with pytest.raises(ValueError):
        await service.suggest_alert_condition(" ", interval="1h")


@pytest.mark.anyio
async def test_suggest_alert_condition_requires_symbol(service: AlertService) -> None:
    with pytest.raises(ValueError):
        await service.suggest_alert_condition("", interval="4h")


def test_fetch_alert_persists_valid_records(
    service: AlertService, in_memory_factory
) -> None:
    user_id = uuid4()
    with in_memory_factory() as session:
        alert = Alert(
            user_id=user_id,
            title="Breakout",
            asset="BTCUSDT",
            condition=">",
            value=50000.0,
            active=True,
        )
        session.add(alert)
        session.commit()

    records = service._fetch_alerts()
    assert len(records) == 1
    assert records[0].asset == "BTCUSDT"


def test_validate_condition_expression_invalid(service: AlertService) -> None:
    with pytest.raises(ValueError):
        service.validate_condition_expression("RSI(14) + >")


def test_toggle_alert_active_repeatedly(
    service: AlertService, in_memory_factory
) -> None:
    user_id = uuid4()
    with in_memory_factory() as session:
        alert = Alert(
            user_id=user_id,
            title="Range",
            asset="ETHUSDT",
            condition="<",
            value=1200.0,
            active=True,
        )
        session.add(alert)
        session.commit()
        alert_id = alert.id

    active_state = True
    for _ in range(4):
        active_state = not active_state
        with in_memory_factory() as session:
            record = session.get(Alert, alert_id)
            assert record is not None
            record.active = active_state
            session.commit()
        results = service._fetch_alerts()
        assert len(results) == (1 if active_state else 0)


@pytest.mark.anyio
async def test_send_with_result_handles_missing_alert(service: AlertService) -> None:
    async def failing_operation():
        raise RuntimeError("alert not found")

    provider, target, error = await service._send_with_result(
        "websocket",
        "missing",
        failing_operation(),
    )

    assert provider == "websocket"
    assert target == "missing"
    assert error == "alert not found"


def test_fetch_alerts_skips_inactive_records(
    service: AlertService, in_memory_factory
) -> None:
    user_id = uuid4()
    with in_memory_factory() as session:
        active_alert = Alert(
            user_id=user_id,
            title="Active",
            asset="AAPL",
            condition=">",
            value=150.0,
            active=True,
        )
        expired_alert = Alert(
            user_id=user_id,
            title="Expired",
            asset="AAPL",
            condition="<",
            value=130.0,
            active=False,
            updated_at=datetime.utcnow() - timedelta(days=1),
        )
        session.add_all([active_alert, expired_alert])
        session.commit()

    records = service._fetch_alerts()
    assert len(records) == 1
    assert records[0].title == "Active"


@pytest.mark.anyio
async def test_evaluate_alerts_handles_invalid_conditions(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = Alert(
        user_id=uuid4(),
        title="Weird",
        asset="BTCUSDT",
        condition="invalid",
        value=100.0,
        active=True,
    )

    monkeypatch.setattr(service, "_fetch_alerts", lambda: [alert])
    monkeypatch.setattr(service, "_resolve_price", AsyncMock(return_value=120.0))

    called = False

    async def fake_notify(alert_obj: Alert, price: float) -> None:  # noqa: ANN001
        nonlocal called
        called = True

    monkeypatch.setattr(service, "_notify", fake_notify)

    await service.evaluate_alerts()

    assert called is False


@pytest.mark.anyio
async def test_evaluate_alerts_skips_alerts_deactivated_during_resolution(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = Alert(
        user_id=uuid4(),
        title="Flip",
        asset="ETHUSDT",
        condition=">",
        value=1500.0,
        active=True,
    )

    async def fake_resolve(symbol: str) -> float:  # noqa: ANN001
        alert.active = False
        return 1600.0

    monkeypatch.setattr(service, "_fetch_alerts", lambda: [alert])
    monkeypatch.setattr(service, "_resolve_price", fake_resolve)
    notifier = AsyncMock()
    monkeypatch.setattr(service, "_notify", notifier)

    await service.evaluate_alerts()

    notifier.assert_not_awaited()


def test_fetch_alerts_reflects_reactivation(
    service: AlertService, in_memory_factory
) -> None:
    user_id = uuid4()
    with in_memory_factory() as session:
        alert = Alert(
            user_id=user_id,
            title="Cycle",
            asset="AAPL",
            condition=">",
            value=150.0,
            active=True,
        )
        session.add(alert)
        session.commit()
        alert_id = alert.id

    assert len(service._fetch_alerts()) == 1

    with in_memory_factory() as session:
        record = session.get(Alert, alert_id)
        assert record is not None
        record.active = False
        session.commit()

    assert len(service._fetch_alerts()) == 0

    with in_memory_factory() as session:
        record = session.get(Alert, alert_id)
        assert record is not None
        record.active = True
        session.commit()

    assert len(service._fetch_alerts()) == 1


@pytest.mark.anyio
async def test_send_external_alert_handles_delivery_exceptions(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    telegram_mock = AsyncMock(side_effect=RuntimeError("telegram down"))
    discord_mock = AsyncMock(side_effect=RuntimeError("discord down"))

    monkeypatch.setattr(service, "_send_telegram_message", telegram_mock)
    monkeypatch.setattr(service, "_send_discord_message", discord_mock)

    results = await service.send_external_alert(
        message="Check",
        telegram_chat_id="123",
        discord_channel_id="456",
    )

    assert results["telegram"]["status"] == "error"
    assert "telegram down" in results["telegram"]["error"]
    assert results["discord"]["status"] == "error"
    assert "discord down" in results["discord"]["error"]


@pytest.mark.anyio
async def test_send_external_alert_requires_target(service: AlertService) -> None:
    with pytest.raises(ValueError):
        await service.send_external_alert(message="Test without targets")


@pytest.mark.anyio
async def test_evaluate_alerts_skips_expired_alerts(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _ExpiringAlert:
        def __init__(self) -> None:
            self.asset = "BTCUSDT"
            self.value = 30000.0
            self.condition = ">"
            self.expires_at = datetime.utcnow() - timedelta(minutes=5)

        @property
        def active(self) -> bool:  # pragma: no cover - simple property
            return self.expires_at > datetime.utcnow()

    alert = _ExpiringAlert()

    monkeypatch.setattr(service, "_fetch_alerts", lambda: [alert])

    async def fail_resolve(symbol: str) -> float:  # noqa: ANN001
        raise AssertionError("Expired alerts should not trigger price resolution")

    monkeypatch.setattr(service, "_resolve_price", fail_resolve)
    notifier = AsyncMock()
    monkeypatch.setattr(service, "_notify", notifier)

    await service.evaluate_alerts()

    notifier.assert_not_awaited()


@pytest.mark.anyio
async def test_evaluate_alerts_triggers_after_reactivation(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = Alert(
        user_id=uuid4(),
        title="Swing",
        asset="AAPL",
        condition=">",
        value=150.0,
        active=True,
    )

    def fetch_alerts() -> list[Alert]:
        return [alert] if getattr(alert, "active", True) else []

    monkeypatch.setattr(service, "_fetch_alerts", fetch_alerts)
    price_resolver = AsyncMock(return_value=180.0)
    monkeypatch.setattr(service, "_resolve_price", price_resolver)
    notifier = AsyncMock()
    monkeypatch.setattr(service, "_notify", notifier)

    # Desactivar temporalmente la alerta
    alert.active = False
    await service.evaluate_alerts()
    notifier.assert_not_awaited()
    price_resolver.assert_not_awaited()

    # Reactivar y comprobar notificación
    alert.active = True
    await service.evaluate_alerts()
    notifier.assert_awaited_once()
    price_resolver.assert_awaited_once()


@pytest.mark.anyio
async def test_send_external_alert_reports_invalid_target(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_telegram(chat_id: str, message: str) -> None:  # noqa: ANN001
        raise RuntimeError(f"invalid target {chat_id}")

    monkeypatch.setattr(service, "_send_telegram_message", failing_telegram)

    results = await service.send_external_alert(
        message="Payload",
        telegram_chat_id="bad-target",
    )

    assert results["telegram"]["status"] == "error"
    assert "bad-target" in results["telegram"]["error"]


def test_should_trigger_equal_condition(service: AlertService) -> None:
    alert = Alert(
        user_id=uuid4(),
        title="Equality",
        asset="BTCUSDT",
        condition="==",
        value=100.0,
        active=True,
    )

    assert service._should_trigger(alert, 100.0000004)
    assert service._should_trigger(alert, 99.9999997)
    assert service._should_trigger(alert, 100.01) is False


def test_should_trigger_unknown_condition_returns_false(service: AlertService) -> None:
    alert = Alert(
        user_id=uuid4(),
        title="Unknown",
        asset="ETHUSDT",
        condition="unsupported",
        value=2000.0,
        active=True,
    )

    assert service._should_trigger(alert, 2100.0) is False


@pytest.mark.anyio
async def test_notify_handles_websocket_errors_and_telegram(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Manager:
        async def broadcast(self, payload):  # noqa: ANN001
            raise RuntimeError("websocket down")

    service.register_websocket_manager(_Manager())

    calls: list[str] = []

    async def fake_notify(alert: Alert, message: str) -> None:  # noqa: ANN001
        calls.append(message)

    monkeypatch.setattr(service, "_notify_telegram", fake_notify)

    alert = Alert(
        user_id=uuid4(),
        title="Breakout",
        asset="ETHUSDT",
        condition=">",
        value=2000.0,
        active=True,
    )

    await service._notify(alert, 2100.0)

    assert calls and "2100.00" in calls[0]


@pytest.mark.anyio
async def test_suggest_alert_condition_fallback_on_ai_error(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_call = AsyncMock(side_effect=RuntimeError("AI offline"))

    monkeypatch.setattr(
        alert_service_module.ai_service,
        "process_message",
        fake_call,
        raising=False,
    )

    suggestion = await service.suggest_alert_condition("btc", interval="4h")

    fake_call.assert_awaited_once()
    assert (
        "Sugerencia" in suggestion["notes"] or "Sugerencia" in suggestion["suggestion"]
    )
    assert suggestion["suggestion"].upper().startswith("BTC")
