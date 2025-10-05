from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.models import Alert, PushSubscription, User
from backend.models.base import Base
from backend.routers import alerts as alerts_router
from backend.services.alerts_service import alerts_service


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

    original_factory = alerts_service._session_factory
    alerts_service._session_factory = test_session_local
    try:
        yield test_session_local
    finally:
        alerts_service._session_factory = original_factory
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(session_factory: sessionmaker) -> Iterator[Session]:
    with session_factory() as session:
        yield session


def _create_user(session: Session) -> User:
    user = User(
        id=uuid.uuid4(), email=f"user_{uuid.uuid4().hex}@test.com", password_hash="hash"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_push_subscription(session: Session, user: User) -> PushSubscription:
    subscription = PushSubscription(
        id=uuid.uuid4(),
        user_id=user.id,
        endpoint=f"https://push.test/{uuid.uuid4().hex}",
        auth="auth-key",
        p256dh="p256dh-key",
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription


def _simple_market_payload() -> dict[str, Any]:
    prices = [100, 99, 98, 97, 96, 95, 94, 93, 92, 90, 88, 86, 84, 82, 80]
    volumes = [1000 + i * 10 for i in range(len(prices))]
    candles = [
        {"high": price + 1, "low": price - 1, "close": price} for price in prices
    ]
    return {
        "prices": prices,
        "volumes": volumes,
        "candles": candles,
        "latest": {"close": 79},
    }


def test_create_alert_simple(session_factory: sessionmaker) -> None:
    with session_factory() as session:
        user = _create_user(session)

    alert = alerts_service.create_alert(
        user.id,
        {
            "name": "RSI Oversold",
            "condition": {"rsi": {"lt": 30}},
        },
    )

    assert alert.name == "RSI Oversold"
    assert alert.active is True
    assert alert.condition == {"rsi": {"lt": 30}}


def test_create_alert_combined_condition(session_factory: sessionmaker) -> None:
    with session_factory() as session:
        user = _create_user(session)

    condition = {"and": [{"rsi": {"lt": 30}}, {"vwap": {"gt": "close"}}]}
    alert = alerts_service.create_alert(
        user.id,
        {
            "name": "RSI y VWAP",
            "condition": condition,
            "delivery_method": "push",
        },
    )

    assert alert.condition == condition


def test_evaluate_alerts_triggers_and_delivers(
    monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    user = _create_user(db)
    _create_push_subscription(db, user)

    alert = alerts_service.create_alert(
        user.id,
        {
            "name": "Alerta compuesta",
            "condition": {"and": [{"rsi": {"lt": 40}}, {"vwap": {"gt": "close"}}]},
        },
    )

    deliveries: list[dict[str, Any]] = []

    def fake_broadcast(subscriptions, payload, category=None):
        deliveries.append({"payload": payload, "category": category})
        return len(list(subscriptions))

    monkeypatch.setattr(
        "backend.services.alerts_service.push_service.broadcast", fake_broadcast
    )

    triggered = alerts_service.evaluate_alerts(_simple_market_payload())

    assert alert.id in triggered
    assert len(deliveries) == 1
    payload = deliveries[0]["payload"]
    assert payload["type"] == "alert"
    assert payload["name"] == "Alerta compuesta"

    db.expire_all()
    stored = db.get(Alert, alert.id)
    assert stored is not None
    assert stored.pending_delivery is True


def test_evaluate_alerts_not_triggered(
    monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    user = _create_user(db)
    _create_push_subscription(db, user)

    alerts_service.create_alert(
        user.id,
        {
            "name": "Condición estricta",
            "condition": {"and": [{"rsi": {"lt": 5}}, {"vwap": {"lt": "close"}}]},
        },
    )

    deliveries: list[dict[str, Any]] = []

    def fake_broadcast(*args, **kwargs):
        deliveries.append({"args": args, "kwargs": kwargs})
        return 0

    monkeypatch.setattr(
        "backend.services.alerts_service.push_service.broadcast", fake_broadcast
    )

    triggered = alerts_service.evaluate_alerts(_simple_market_payload())

    assert triggered == []
    assert deliveries == []


def test_evaluate_alert_without_subscriptions_marks_pending(db: Session) -> None:
    user = _create_user(db)
    alerts_service.create_alert(
        user.id,
        {
            "name": "Sin subscripción",
            "condition": {"rsi": {"lt": 100}},
        },
    )

    triggered = alerts_service.evaluate_alerts(_simple_market_payload())
    assert triggered  # condición siempre verdadera

    db.expire_all()
    stored_alerts = db.query(Alert).all()
    assert stored_alerts[0].pending_delivery is False


@pytest_asyncio.fixture()
async def api_client(session_factory: sessionmaker) -> AsyncIterator[AsyncClient]:
    user_container: dict[str, User] = {}

    async def _fake_current_user() -> User:
        return user_container["user"]

    app.dependency_overrides[alerts_router.get_current_user] = _fake_current_user

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            with session_factory() as session:
                user_container["user"] = _create_user(session)
            yield client
    finally:
        app.dependency_overrides.pop(alerts_router.get_current_user, None)


@pytest.mark.asyncio
async def test_alert_endpoints_crud(api_client: AsyncClient) -> None:
    create_payload = {
        "name": "VWAP alert",
        "condition": {"vwap": {"gt": 100}},
    }
    response = await api_client.post("/api/alerts", json=create_payload)
    assert response.status_code == 201, response.text
    alert_id = response.json()["id"]

    listing = await api_client.get("/api/alerts")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    toggle = await api_client.patch(
        f"/api/alerts/{alert_id}/toggle",
        json={"active": False},
    )
    assert toggle.status_code == 200
    assert toggle.json()["active"] is False

    delete = await api_client.delete(f"/api/alerts/{alert_id}")
    assert delete.status_code == 200

    listing_after = await api_client.get("/api/alerts")
    assert listing_after.status_code == 200
    assert listing_after.json() == []
