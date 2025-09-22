import asyncio
import os
import sys
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.alert_service import AlertService


def test_alert_service_triggers_notification():
    alert = SimpleNamespace(
        id=1,
        symbol="AAPL",
        comparison="above",
        target_price=100.0,
        message=None,
        telegram_chat_id=None,
    )

    service = AlertService(session_factory=True)
    service._session_factory = True  # type: ignore[attr-defined]
    service._fetch_active_alerts = lambda: [alert]  # type: ignore[assignment]
    service._mark_triggered = lambda alerts: None  # type: ignore[assignment]

    async def fake_price(symbol):  # noqa: ANN001
        return 105.0

    notified = []

    async def fake_notify(alert_obj, price):  # noqa: ANN001
        notified.append((alert_obj, price))

    service._resolve_price = fake_price  # type: ignore[assignment]
    service._notify = fake_notify  # type: ignore[assignment]

    asyncio.run(service.evaluate_alerts())

    assert notified == [(alert, 105.0)]


def test_alert_service_should_trigger_conditions():
    service = AlertService(session_factory=None)

    alert_above = SimpleNamespace(comparison="above", target_price=10.0)
    alert_below = SimpleNamespace(comparison="below", target_price=10.0)
    alert_equal = SimpleNamespace(comparison="equal", target_price=10.0)

    assert service._should_trigger(alert_above, 10.0) is True
    assert service._should_trigger(alert_below, 9.5) is True
    assert service._should_trigger(alert_equal, 10.0000001) is True
    assert service._should_trigger(alert_equal, 10.1) is False
