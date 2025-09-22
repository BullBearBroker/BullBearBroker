"""End-to-end API tests for the BullBearBroker FastAPI application."""

from __future__ import annotations

import asyncio
import os
import uuid
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

# Ensure the backend package is importable when running from the tests directory.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# The real UserService requires a PostgreSQL connection string. Provide a dummy
# one so the import does not fail when modules are loaded during the tests.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/testdb")

from app.main import app, alert_service  # noqa: E402  (import after path setup)
from routers import alerts as alerts_router  # noqa: E402
from routers import auth as auth_router  # noqa: E402
from services.market_service import market_service  # noqa: E402
from services.news_service import news_service  # noqa: E402
from services.forex_service import forex_service  # noqa: E402
import importlib

news_service_module = importlib.import_module("services.news_service")


class DummyAsyncCache:
    """Minimal async cache used to avoid hitting Redis during tests."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:  # noqa: D401
        # ``ttl`` is ignored because tests do not need expiration semantics.
        self._store[key] = value


class DummyAsyncSessionContext:
    """Simple async context manager replacing aiohttp sessions."""

    async def __aenter__(self) -> SimpleNamespace:
        return SimpleNamespace()

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        return None


@dataclass
class DummyUser:
    """Lightweight user entity mimicking the SQLAlchemy model."""

    id: uuid.UUID
    email: str
    password: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def verify_password(self, password: str) -> bool:
        return self.password == password


@dataclass
class DummyAlert:
    """In-memory alert representation used by the API tests."""

    id: uuid.UUID
    user_id: uuid.UUID
    asset: str
    value: float
    condition: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class DummyUserService:
    """Replacement for the database backed user service."""

    class UserAlreadyExistsError(Exception):
        pass

    class UserNotFoundError(Exception):
        pass

    class InvalidCredentialsError(Exception):
        pass

    def __init__(self) -> None:
        self._users: Dict[str, DummyUser] = {}
        self._sessions: List[SimpleNamespace] = []
        self._alerts: Dict[uuid.UUID, List[DummyAlert]] = {}

    def create_user(self, email: str, password: str) -> DummyUser:
        if email in self._users:
            raise self.UserAlreadyExistsError("Email ya está registrado")

        user = DummyUser(id=uuid.uuid4(), email=email, password=password)
        self._users[email] = user
        self._alerts[user.id] = []
        return user

    def get_user_by_email(self, email: str) -> Optional[DummyUser]:
        return self._users.get(email)

    def authenticate_user(self, email: str, password: str) -> DummyUser:
        user = self.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise self.InvalidCredentialsError("Credenciales inválidas")
        return user

    def create_session(
        self, user_id: uuid.UUID, token: str, expires_in: Optional[timedelta] = None
    ) -> SimpleNamespace:
        expires_at = (
            datetime.utcnow() + expires_in if expires_in is not None else None
        )
        session = SimpleNamespace(user_id=user_id, token=token, expires_at=expires_at)
        self._sessions.append(session)
        return session

    def register_session_activity(self, token: str) -> None:  # noqa: D401
        # The real service updates the session timestamp. Tests do not need it.
        return None

    def create_alert(
        self,
        user_id: uuid.UUID,
        *,
        asset: str,
        value: float,
        condition: str,
    ) -> DummyAlert:
        if user_id not in self._alerts:
            raise self.UserNotFoundError("Usuario no encontrado")

        alert = DummyAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            asset=asset,
            value=value,
            condition=condition,
        )
        self._alerts[user_id].append(alert)
        return alert

    def get_alerts_for_user(self, user_id: uuid.UUID) -> List[DummyAlert]:
        return list(self._alerts.get(user_id, []))


@pytest.fixture()
def dummy_user_service(monkeypatch: pytest.MonkeyPatch) -> DummyUserService:
    """Provide a patched user service for authentication and alerts routes."""

    service = DummyUserService()

    monkeypatch.setattr(auth_router, "user_service", service)
    monkeypatch.setattr(alerts_router, "user_service", service)
    monkeypatch.setattr(auth_router, "UserAlreadyExistsError", service.UserAlreadyExistsError)
    monkeypatch.setattr(alerts_router, "UserNotFoundError", service.UserNotFoundError)
    monkeypatch.setattr(auth_router, "InvalidCredentialsError", service.InvalidCredentialsError)
    monkeypatch.setattr(alerts_router, "USER_SERVICE_ERROR", None)
    monkeypatch.setattr(auth_router, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(alerts_router, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(auth_router, "ALGORITHM", "HS256")
    monkeypatch.setattr(alerts_router, "ALGORITHM", "HS256")

    return service


@pytest.fixture()
def client(dummy_user_service: DummyUserService, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient instance with background services neutralised."""

    async def noop_start() -> None:
        return None

    async def noop_stop() -> None:
        return None

    monkeypatch.setattr(alert_service, "register_websocket_manager", lambda manager: None)
    monkeypatch.setattr(alert_service, "start", noop_start)
    monkeypatch.setattr(alert_service, "stop", noop_stop)
    monkeypatch.setattr(alert_service, "is_running", False)

    return TestClient(app)


def _reset_crypto_service(monkeypatch: pytest.MonkeyPatch) -> None:
    crypto_service = market_service.crypto_service
    crypto_service.cache = DummyAsyncCache()
    crypto_service._coingecko_id_cache.clear()
    market_service.binance_cache.clear()
    monkeypatch.setattr(crypto_service, "RETRY_ATTEMPTS", 1, raising=False)


def _prepare_stock_service(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    stock_service = market_service.stock_service
    stock_service.cache = DummyAsyncCache()
    stock_service.apis[0]["api_key"] = "dummy-twelvedata"
    stock_service.apis[2]["api_key"] = "dummy-alpha"
    monkeypatch.setattr(stock_service, "_session_factory", lambda timeout=None: DummyAsyncSessionContext())
    call_order: List[str] = []

    async def fake_call_with_retries(handler, session, symbol, source_name):  # noqa: ANN001
        call_order.append(source_name)
        responses = {
            "Twelve Data": None,
            "Yahoo Finance": {"price": 123.45, "change": 1.2},
            "Alpha Vantage": {"price": 0.0, "change": 0.0},
        }
        return responses.get(source_name)

    monkeypatch.setattr(stock_service, "_call_with_retries", fake_call_with_retries)
    return {"calls": call_order}


def _prepare_forex_service(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    forex_service.cache = DummyAsyncCache()
    forex_service.apis[0]["api_key"] = "dummy-twelvedata"
    monkeypatch.setattr(forex_service, "_session_factory", lambda timeout=None: DummyAsyncSessionContext())
    call_order: List[str] = []

    async def fake_fx_call_with_retries(handler, session, symbol, source_name):  # noqa: ANN001
        call_order.append(source_name)
        responses = {
            "Twelve Data": None,
            "Yahoo Finance": {"price": 1.2345, "change": 0.01},
        }
        return responses.get(source_name)

    monkeypatch.setattr(forex_service, "_call_with_retries", fake_fx_call_with_retries)
    return {"calls": call_order}


def _prepare_news_service(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    news_service.cache = DummyAsyncCache()
    monkeypatch.setattr(news_service, "_session_factory", lambda timeout=None: DummyAsyncSessionContext())
    call_order: List[str] = []

    async def fake_news_call_with_retries(handler, session, limit, **kwargs):  # noqa: ANN001
        call_order.append(handler.__name__)
        responses = {
            "_fetch_cryptopanic": [],
            "_fetch_newsapi": [
                {
                    "source": "NewsAPI",
                    "title": "Fallback crypto headline",
                    "url": "https://example.com/news/crypto",
                    "published_at": datetime.utcnow().isoformat(),
                    "summary": "Fallback content",
                }
            ],
            "_fetch_finfeed": [
                {
                    "source": "Finfeed",
                    "title": "Primary finance headline",
                    "url": "https://example.com/news/finance",
                    "published_at": datetime.utcnow().isoformat(),
                    "summary": "Primary content",
                }
            ],
        }
        return responses.get(handler.__name__, [])

    monkeypatch.setattr(news_service, "_call_with_retries", fake_news_call_with_retries)
    return {"calls": call_order}


def test_register_creates_user_and_returns_token(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "secret1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "alice@example.com"
    assert isinstance(payload["token"], str) and payload["token"]


def test_login_returns_token_for_valid_credentials(
    client: TestClient, dummy_user_service: DummyUserService
) -> None:
    dummy_user_service.create_user(email="bob@example.com", password="hunter2")

    response = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "hunter2"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "bob@example.com"
    assert isinstance(payload["token"], str)


def test_login_rejects_invalid_credentials(
    client: TestClient, dummy_user_service: DummyUserService
) -> None:
    dummy_user_service.create_user(email="charlie@example.com", password="topsecret")

    response = client.post(
        "/api/auth/login",
        json={"email": "charlie@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_crypto_endpoint_uses_primary_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_crypto_service(monkeypatch)
    crypto_service = market_service.crypto_service
    provider_calls: List[str] = []

    async def fake_coingecko(symbol: str) -> float:
        provider_calls.append("coingecko")
        return 45000.0

    async def fake_binance_provider(symbol: str) -> Optional[float]:
        provider_calls.append("binance")
        return None

    async def fake_coinmarketcap(symbol: str) -> Optional[float]:
        provider_calls.append("coinmarketcap")
        return None

    monkeypatch.setattr(crypto_service, "coingecko", fake_coingecko)
    monkeypatch.setattr(crypto_service, "binance", fake_binance_provider)
    monkeypatch.setattr(crypto_service, "coinmarketcap", fake_coinmarketcap)
    binance_mock = AsyncMock(return_value={"price": "45100", "source": "Binance"})
    monkeypatch.setattr(market_service, "get_binance_price", binance_mock)

    response = client.get("/crypto/btc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == 45000.0
    assert payload["source"] == "CryptoService + Binance"
    assert provider_calls == ["coingecko"]
    assert binance_mock.await_count == 1


def test_crypto_endpoint_falls_back_to_coinmarketcap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_crypto_service(monkeypatch)
    crypto_service = market_service.crypto_service
    provider_calls: List[str] = []

    async def fake_coingecko(symbol: str) -> Optional[float]:
        provider_calls.append("coingecko")
        return None

    async def fake_binance_provider(symbol: str) -> Optional[float]:
        provider_calls.append("binance")
        return None

    async def fake_coinmarketcap(symbol: str) -> Optional[float]:
        provider_calls.append("coinmarketcap")
        return 123.45

    monkeypatch.setattr(crypto_service, "coingecko", fake_coingecko)
    monkeypatch.setattr(crypto_service, "binance", fake_binance_provider)
    monkeypatch.setattr(crypto_service, "coinmarketcap", fake_coinmarketcap)
    monkeypatch.setattr(
        market_service,
        "get_binance_price",
        AsyncMock(return_value={"price": "123.40", "source": "Binance"}),
    )

    response = client.get("/crypto/eth")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == 123.45
    assert payload["source"] == "CryptoService + Binance"
    assert provider_calls == ["coingecko", "binance", "coinmarketcap"]


def test_crypto_endpoint_returns_404_when_no_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_crypto_service(monkeypatch)
    crypto_service = market_service.crypto_service

    async def always_none(symbol: str) -> Optional[float]:
        return None

    monkeypatch.setattr(crypto_service, "coingecko", always_none)
    monkeypatch.setattr(crypto_service, "binance", always_none)
    monkeypatch.setattr(crypto_service, "coinmarketcap", always_none)
    monkeypatch.setattr(market_service, "get_binance_price", AsyncMock(return_value=None))

    response = client.get("/crypto/xrp")
    assert response.status_code == 404
    assert "No se encontró información" in response.json()["detail"]


def test_stock_endpoint_uses_fallback_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _prepare_stock_service(monkeypatch)

    response = client.get("/stock/AAPL")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == pytest.approx(123.45)
    assert payload["source"] == "Yahoo Finance"
    assert info["calls"] == ["Twelve Data", "Yahoo Finance"]


def test_forex_endpoint_falls_back_to_yahoo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _prepare_forex_service(monkeypatch)

    response = client.get("/forex/EURUSD")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == pytest.approx(1.2345)
    assert payload["source"] == "Yahoo Finance"
    assert info["calls"] == ["Twelve Data", "Yahoo Finance"]


def test_news_endpoints_use_fallbacks(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    info = _prepare_news_service(monkeypatch)
    monkeypatch.setattr(news_service_module.Config, "CRYPTOPANIC_API_KEY", "token")
    monkeypatch.setattr(news_service_module.Config, "NEWSAPI_API_KEY", "token")
    monkeypatch.setattr(news_service_module.Config, "FINFEED_API_KEY", "token")
    monkeypatch.setattr(news_service, "cache", DummyAsyncCache())

    crypto_response = client.get("/news/crypto")
    assert crypto_response.status_code == 200
    crypto_payload = crypto_response.json()
    assert crypto_payload["category"] == "crypto"
    assert len(crypto_payload["articles"]) == 1

    finance_response = client.get("/news/finance")
    assert finance_response.status_code == 200
    finance_payload = finance_response.json()
    assert finance_payload["category"] == "finance"
    assert len(finance_payload["articles"]) == 1

    assert info["calls"] == ["_fetch_cryptopanic", "_fetch_newsapi", "_fetch_finfeed"]


def test_alert_workflow_triggers_notification(
    client: TestClient,
    dummy_user_service: DummyUserService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register = client.post(
        "/api/auth/register",
        json={"email": "alert@example.com", "password": "alerts1"},
    )
    assert register.status_code == 200
    token = register.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/alerts",
        json={"asset": "AAPL", "value": 100.0, "condition": "above"},
        headers=headers,
    )
    assert response.status_code == 201

    user_id = uuid.UUID(register.json()["user"]["id"])
    created_alert = dummy_user_service.get_alerts_for_user(user_id)[0]
    notifications: List[Dict[str, Any]] = []

    def fake_fetch_alerts() -> List[DummyAlert]:  # noqa: D401
        return [created_alert]

    async def fake_resolve_price(symbol: str) -> Optional[float]:  # noqa: ANN001
        return 120.0

    async def fake_notify(alert, price):  # noqa: ANN001
        notifications.append({"alert": alert, "price": price})

    monkeypatch.setattr(alert_service, "_session_factory", True)
    monkeypatch.setattr(alert_service, "_fetch_alerts", fake_fetch_alerts)
    monkeypatch.setattr(alert_service, "_resolve_price", fake_resolve_price)
    monkeypatch.setattr(alert_service, "_notify", fake_notify)

    asyncio.run(alert_service.evaluate_alerts())

    assert notifications and notifications[0]["price"] == 120.0
    assert notifications[0]["alert"].id == created_alert.id


def test_alerts_list_returns_created_alert(
    client: TestClient,
    dummy_user_service: DummyUserService,
) -> None:
    register = client.post(
        "/api/auth/register",
        json={"email": "list@example.com", "password": "alerts1"},
    )
    token = register.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = client.post(
        "/alerts",
        json={"asset": "ETH", "value": 1500.0, "condition": "below"},
        headers=headers,
    )
    assert create.status_code == 201

    listing = client.get("/alerts", headers=headers)
    assert listing.status_code == 200
    alerts = listing.json()
    assert len(alerts) == 1
    assert alerts[0]["asset"] == "ETH"
    assert alerts[0]["condition"] == "below"
