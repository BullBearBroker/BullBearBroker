from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.alert import Alert
from backend.models.base import Base
from backend.services.alert_service import AlertService


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


def test_fetch_alert_persists_valid_records(service: AlertService, in_memory_factory) -> None:
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


def test_toggle_alert_active_repeatedly(service: AlertService, in_memory_factory) -> None:
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


def test_fetch_alerts_skips_inactive_records(service: AlertService, in_memory_factory) -> None:
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
