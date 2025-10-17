from datetime import datetime, timedelta
from importlib import import_module
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Alert, Base

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


@pytest.fixture()
def service(in_memory_factory) -> AlertService:
    svc = AlertService(session_factory=in_memory_factory)
    svc.register_websocket_manager(None)
    return svc


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_send_external_alert_without_targets_raises(
    service: AlertService,
) -> None:
    with pytest.raises(ValueError):
        await service.send_external_alert(message="hola")


@pytest.mark.anyio
async def test_send_external_alert_reports_delivery_failure(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        alert_service_module.Config,
        "TELEGRAM_DEFAULT_CHAT_ID",
        "12345",
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_send_telegram_message",
        AsyncMock(side_effect=RuntimeError("telegram down")),
    )

    result = await service.send_external_alert(message="hola", telegram_chat_id="12345")

    assert result["telegram"]["status"] == "error"
    assert "telegram down" in result["telegram"]["error"]


@pytest.mark.anyio
async def test_notify_tolerates_websocket_and_telegram_failures(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = Alert(
        id=uuid4(),
        user_id=uuid4(),
        title="Breakout",
        asset="BTCUSDT",
        condition=">",
        value=45000.0,
        active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    class BrokenManager:
        async def broadcast(self, payload):  # noqa: ANN001
            raise RuntimeError("websocket offline")

    service.register_websocket_manager(BrokenManager())
    monkeypatch.setattr(
        alert_service_module.Config,
        "TELEGRAM_DEFAULT_CHAT_ID",
        "12345",
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_send_telegram_message",
        AsyncMock(side_effect=RuntimeError("telegram offline")),
    )

    await service._notify(alert, price=45500.0)

    service._send_telegram_message.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_evaluate_alerts_handles_reactivation_flow(
    service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = Alert(
        id=uuid4(),
        user_id=uuid4(),
        title="Support",
        asset="ETHUSDT",
        condition=">",
        value=1800.0,
        active=False,
        created_at=datetime.utcnow() - timedelta(days=1),
        updated_at=datetime.utcnow() - timedelta(hours=2),
    )

    alerts = [alert]

    monkeypatch.setattr(service, "_fetch_alerts", lambda: alerts)
    price_resolver = AsyncMock(return_value=1900.0)
    monkeypatch.setattr(service, "_resolve_price", price_resolver)
    notifier = AsyncMock()
    monkeypatch.setattr(service, "_notify", notifier)

    await service.evaluate_alerts()
    notifier.assert_not_awaited()

    alert.active = True
    await service.evaluate_alerts()

    notifier.assert_awaited_once_with(alert, 1900.0)
