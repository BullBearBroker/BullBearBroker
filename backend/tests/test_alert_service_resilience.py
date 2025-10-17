from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.alert_service as alert_module
from backend.models import Base
from backend.models.alert import Alert
from backend.services.alert_service import AlertService


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def alert_service(session_factory) -> AlertService:
    service = AlertService(session_factory=session_factory)
    service._telegram_token = None
    service._discord_token = None
    return service


@pytest.mark.anyio
async def test_suggest_alert_condition_requires_symbol(
    alert_service: AlertService,
) -> None:
    with pytest.raises(ValueError):
        await alert_service.suggest_alert_condition("   ")


def test_validate_condition_expression_detects_corruption(
    alert_service: AlertService,
) -> None:
    with pytest.raises(ValueError):
        alert_service.validate_condition_expression("RSI(14) > & MACD()")


@pytest.mark.anyio
async def test_evaluate_alerts_respects_repeated_toggle(
    alert_service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = SimpleNamespace(
        asset="ETHUSDT",
        value=1800.0,
        condition=">",
        active=True,
    )

    monkeypatch.setattr(alert_service, "_fetch_alerts", lambda: [alert])
    price_provider = AsyncMock(return_value=1900.0)
    notifier = AsyncMock()

    monkeypatch.setattr(alert_service, "_resolve_price", price_provider)
    monkeypatch.setattr(alert_service, "_notify", notifier)

    await alert_service.evaluate_alerts()
    notifier.assert_awaited_once()

    alert.active = False
    await alert_service.evaluate_alerts()
    assert notifier.await_count == 1

    alert.active = True
    await alert_service.evaluate_alerts()
    assert notifier.await_count == 2


@pytest.mark.anyio
async def test_evaluate_alerts_ignores_expired_entries(
    alert_service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ExpiringAlert(SimpleNamespace):
        @property
        def active(self) -> bool:  # pragma: no cover - trivial property
            return self.expires_at > datetime.utcnow()

    expired = ExpiringAlert(
        asset="BTCUSDT",
        value=30000.0,
        condition=">",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )

    monkeypatch.setattr(alert_service, "_fetch_alerts", lambda: [expired])
    price_provider = AsyncMock()
    notifier = AsyncMock()

    monkeypatch.setattr(alert_service, "_resolve_price", price_provider)
    monkeypatch.setattr(alert_service, "_notify", notifier)

    await alert_service.evaluate_alerts()

    price_provider.assert_not_awaited()
    notifier.assert_not_awaited()


@pytest.mark.anyio
async def test_notify_tolerates_external_failures(
    alert_service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = Alert(
        user_id=uuid4(),
        title="Breakout",
        asset="AAPL",
        condition=">",
        value=150.0,
        active=True,
    )

    class BrokenManager:
        async def broadcast(self, payload):  # noqa: ANN001
            raise RuntimeError("ws down")

    alert_service.register_websocket_manager(BrokenManager())

    alert_service._telegram_token = "token"
    monkeypatch.setattr(
        alert_module,
        "Config",
        SimpleNamespace(TELEGRAM_DEFAULT_CHAT_ID="123"),
        raising=False,
    )
    monkeypatch.setattr(alert_service, "_telegram_bot", None, raising=False)

    async def failing_send(chat_id: str, message: str) -> None:  # noqa: ANN001
        raise RuntimeError("telegram failure")

    monkeypatch.setattr(alert_service, "_send_telegram_message", failing_send)

    # No exception should escape even if both channels fail
    await alert_service._notify(alert, price=151.5)


def test_validate_condition_expression_rejects_blank(
    alert_service: AlertService,
) -> None:
    with pytest.raises(ValueError):
        alert_service.validate_condition_expression("   ")


@pytest.mark.anyio
async def test_evaluate_alerts_ignores_corrupt_prices(
    alert_service: AlertService, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = SimpleNamespace(
        asset="SOLUSDT",
        value=25.0,
        condition=">",
        active=True,
    )

    monkeypatch.setattr(alert_service, "_fetch_alerts", lambda: [alert])
    monkeypatch.setattr(alert_service, "_resolve_price", AsyncMock(return_value=None))
    notifier = AsyncMock()
    monkeypatch.setattr(alert_service, "_notify", notifier)

    await alert_service.evaluate_alerts()
    notifier.assert_not_awaited()


@pytest.mark.anyio
async def test_resolve_price_handles_non_numeric_payload(
    monkeypatch: pytest.MonkeyPatch, alert_service: AlertService
) -> None:
    class FlakyMarket:
        async def get_stock_price(self, symbol):  # noqa: ANN001
            return {"price": None}

        async def get_crypto_price(self, symbol):  # noqa: ANN001
            return {"price": "not-a-number"}

    class FlakyForex:
        async def get_quote(self, symbol):  # noqa: ANN001
            return {"price": None}

    monkeypatch.setattr(alert_module, "market_service", FlakyMarket(), raising=False)
    monkeypatch.setattr(alert_module, "forex_service", FlakyForex(), raising=False)

    result = await alert_service._resolve_price("EURUSD")
    assert result is None
