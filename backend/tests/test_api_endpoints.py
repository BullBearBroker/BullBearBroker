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

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

# Ensure optional dependencies are stubbed before importing FastAPI / app modules.
ensure_test_dependencies()

# Ensure the backend package is importable when running from the tests directory.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# The real UserService requires a PostgreSQL connection string. Provide a dummy
# one so the import does not fail when modules are loaded during the tests.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/testdb")

from backend.main import app  # noqa: E402  (import after path setup)
from backend.routers import alerts as alerts_router  # noqa: E402
from backend.routers import auth as auth_router  # noqa: E402
from backend.services.alert_service import alert_service  # noqa: E402
from backend.services.market_service import market_service  # noqa: E402
from backend.services.news_service import news_service  # noqa: E402
from backend.services.forex_service import forex_service  # noqa: E402
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

    class InvalidTokenError(Exception):
        pass

    def __init__(self) -> None:
        self._users: Dict[str, DummyUser] = {}
        self._users_by_id: Dict[uuid.UUID, DummyUser] = {}
        self._sessions: List[SimpleNamespace] = []
        self._alerts: Dict[uuid.UUID, List[DummyAlert]] = {}
        self._refresh_tokens: Dict[str, SimpleNamespace] = {}
        self._secret = "test-secret"
        self._algorithm = "HS256"

    def create_user(self, email: str, password: str) -> DummyUser:
        if email in self._users:
            raise self.UserAlreadyExistsError("Email ya está registrado")

        user = DummyUser(id=uuid.uuid4(), email=email, password=password)
        self._users[email] = user
        self._users_by_id[user.id] = user
        self._alerts[user.id] = []
        return user

    def get_user_by_email(self, email: str) -> Optional[DummyUser]:
        return self._users.get(email)

    def authenticate_user(self, email: str, password: str) -> DummyUser:
        user = self.get_user_by_email(email)
        if not user or not user.verify_password(password):
            raise self.InvalidCredentialsError("Credenciales inválidas")
        return user

    def _build_payload(self, user: DummyUser, expires_at: datetime) -> Dict[str, Any]:
        now = datetime.utcnow()
        return {
            "sub": str(user.id),
            "user_id": str(user.id),
            "email": user.email,
            "iat": now,
            "nbf": now,
            "exp": expires_at,
        }

    def _decode_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover - deterministic tests
            raise self.InvalidTokenError("Token expirado") from exc
        except jwt.InvalidTokenError as exc:
            raise self.InvalidTokenError("Token inválido") from exc

    @staticmethod
    def _extract_exp(payload: Dict[str, Any]) -> datetime:
        exp = payload.get("exp")
        if isinstance(exp, datetime):
            return exp
        if isinstance(exp, (int, float)):
            return datetime.utcfromtimestamp(exp)
        raise DummyUserService.InvalidTokenError("Token inválido")

    @staticmethod
    def _extract_user_id(payload: Dict[str, Any]) -> uuid.UUID:
        raw_user_id = payload.get("user_id") or payload.get("sub")
        if not raw_user_id:
            raise DummyUserService.InvalidTokenError("Token inválido")
        try:
            return uuid.UUID(str(raw_user_id))
        except ValueError as exc:
            raise DummyUserService.InvalidTokenError("Token inválido") from exc

    def create_access_token(
        self, user: DummyUser, expires_in: Optional[timedelta] = None
    ) -> tuple[str, datetime]:
        expires_at = datetime.utcnow() + (expires_in or timedelta(minutes=15))
        payload = self._build_payload(user, expires_at)
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def create_session(
        self,
        user_id: uuid.UUID,
        token: Optional[str] = None,
        expires_in: Optional[timedelta] = None,
    ) -> tuple[str, SimpleNamespace]:
        user = self._users_by_id.get(user_id)
        if not user:
            raise self.UserNotFoundError("Usuario no encontrado")

        if token is None:
            token, expires_at = self.create_access_token(user, expires_in)
        else:
            payload = self._decode_token(token)
            payload_user_id = self._extract_user_id(payload)
            if payload_user_id != user_id:
                raise self.InvalidTokenError("Token inválido")
            expires_at = self._extract_exp(payload)

        session = SimpleNamespace(user_id=user_id, token=token, expires_at=expires_at)
        self._sessions.append(session)
        return token, session

    def register_session_activity(self, token: str) -> None:  # noqa: D401
        # The real service updates the session timestamp. Tests do not need it.
        return None

    def get_current_user(self, token: str) -> DummyUser:
        payload = self._decode_token(token)
        user_id = self._extract_user_id(payload)

        now = datetime.utcnow()
        if not any(
            sess.token == token and sess.user_id == user_id and sess.expires_at > now
            for sess in self._sessions
        ):
            raise self.InvalidTokenError("Token inválido")

        user = self._users_by_id.get(user_id)
        if not user:
            raise self.InvalidTokenError("Token inválido")
        return user

    def create_refresh_token(
        self, user: DummyUser, expires_in: Optional[timedelta] = None
    ) -> tuple[str, datetime]:
        expires_at = datetime.utcnow() + (expires_in or timedelta(days=7))
        token = jwt.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "exp": expires_at,
            },
            self._secret,
            algorithm=self._algorithm,
        )
        self._refresh_tokens[token] = SimpleNamespace(user_id=user.id, expires_at=expires_at)
        return token, expires_at

    def rotate_refresh_token(self, refresh_token: str) -> tuple[DummyUser, str, datetime]:
        stored = self._refresh_tokens.pop(refresh_token, None)
        if not stored or stored.expires_at <= datetime.utcnow():
            raise self.InvalidTokenError("Refresh token inválido")
        user = self._users_by_id.get(stored.user_id)
        if not user:
            raise self.InvalidTokenError("Usuario no encontrado")
        new_refresh, expires_at = self.create_refresh_token(user)
        return user, new_refresh, expires_at

    def issue_token_pair(
        self, user: DummyUser
    ) -> tuple[str, datetime, str, datetime]:
        access_token, session = self.create_session(user.id)
        refresh_token, refresh_expires = self.create_refresh_token(user)
        return access_token, session.expires_at, refresh_token, refresh_expires

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
    monkeypatch.setattr(auth_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "USER_SERVICE_ERROR", None)

    return service


@pytest_asyncio.fixture()
async def client(
    dummy_user_service: DummyUserService, monkeypatch: pytest.MonkeyPatch
) -> AsyncClient:
    """Return an AsyncClient instance with background services neutralised."""

    async def noop_start() -> None:
        return None

    async def noop_stop() -> None:
        return None

    monkeypatch.setattr(alert_service, "register_websocket_manager", lambda manager: None)
    monkeypatch.setattr(alert_service, "start", noop_start)
    monkeypatch.setattr(alert_service, "stop", noop_stop)
    monkeypatch.setattr(alert_service, "is_running", False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


def _reset_crypto_service(monkeypatch: pytest.MonkeyPatch) -> None:
    crypto_service = market_service.crypto_service
    crypto_service.cache = DummyAsyncCache()
    crypto_service._coingecko_id_cache.clear()
    market_service.binance_cache.clear()
    monkeypatch.setattr(crypto_service, "RETRY_ATTEMPTS", 1, raising=False)

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        alt_market_service = alt_module.market_service
        alt_crypto_service = alt_market_service.crypto_service
        alt_crypto_service.cache = DummyAsyncCache()
        alt_crypto_service._coingecko_id_cache.clear()
        alt_market_service.binance_cache.clear()
        monkeypatch.setattr(alt_crypto_service, "RETRY_ATTEMPTS", 1, raising=False)


def _prepare_stock_service(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    stock_service = market_service.stock_service
    stock_service.cache = DummyAsyncCache()
    stock_service.apis[0]["api_key"] = "dummy-alpha"
    stock_service.apis[1]["api_key"] = "dummy-twelvedata"
    monkeypatch.setattr(stock_service, "_session_factory", lambda timeout=None: DummyAsyncSessionContext())
    call_order: List[str] = []

    async def fake_call_with_retries(handler, session, symbol, source_name):  # noqa: ANN001
        call_order.append(source_name)
        responses = {
            "Alpha Vantage": None,
            "Twelve Data": None,
            "Yahoo Finance": {"price": 123.45, "change": 1.2},
        }
        return responses.get(source_name)

    monkeypatch.setattr(stock_service, "_call_with_retries", fake_call_with_retries)

    alt_market_module = sys.modules.get("services.market_service")
    if alt_market_module is not None:
        alt_stock_service = alt_market_module.market_service.stock_service
        alt_stock_service.cache = DummyAsyncCache()
        alt_stock_service.apis[0]["api_key"] = "dummy-alpha"
        alt_stock_service.apis[1]["api_key"] = "dummy-twelvedata"
        monkeypatch.setattr(
            alt_stock_service,
            "_session_factory",
            lambda timeout=None: DummyAsyncSessionContext(),
        )

        async def alt_fake_call_with_retries(handler, session, symbol, source_name):  # noqa: ANN001
            call_order.append(source_name)
            responses = {
                "Alpha Vantage": None,
                "Twelve Data": None,
                "Yahoo Finance": {"price": 123.45, "change": 1.2},
            }
            return responses.get(source_name)

        monkeypatch.setattr(alt_stock_service, "_call_with_retries", alt_fake_call_with_retries)

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

    alt_forex_module = sys.modules.get("services.forex_service")
    if alt_forex_module is not None:
        alt_forex_service = alt_forex_module.forex_service
        alt_forex_service.cache = DummyAsyncCache()
        alt_forex_service.apis[0]["api_key"] = "dummy-twelvedata"
        monkeypatch.setattr(
            alt_forex_service,
            "_session_factory",
            lambda timeout=None: DummyAsyncSessionContext(),
        )

        async def alt_fake_fx_call_with_retries(handler, session, symbol, source_name):  # noqa: ANN001
            call_order.append(source_name)
            responses = {
                "Twelve Data": None,
                "Yahoo Finance": {"price": 1.2345, "change": 0.01},
            }
            return responses.get(source_name)

        monkeypatch.setattr(alt_forex_service, "_call_with_retries", alt_fake_fx_call_with_retries)

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

    alt_news_module = sys.modules.get("services.news_service")
    if alt_news_module is not None:
        alt_service = getattr(alt_news_module, "news_service", None)
        if alt_service is not None:
            alt_service.cache = DummyAsyncCache()
            monkeypatch.setattr(
                alt_service,
                "_session_factory",
                lambda timeout=None: DummyAsyncSessionContext(),
            )
            monkeypatch.setattr(alt_service, "_call_with_retries", fake_news_call_with_retries)

    return {"calls": call_order}



@pytest.mark.asyncio
async def test_register_creates_user_and_returns_profile(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "secret1"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "alice@example.com"
    assert set(payload.keys()) == {"id", "email", "created_at"}
    assert payload["created_at"]


@pytest.mark.asyncio
async def test_login_returns_token_for_valid_credentials(
    client: AsyncClient, dummy_user_service: DummyUserService
) -> None:
    dummy_user_service.create_user(email="bob@example.com", password="hunter2")

    response = await client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "hunter2"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "bob@example.com"
    assert isinstance(payload["access_token"], str)
    assert isinstance(payload["refresh_token"], str)
    assert payload["token_type"] == "bearer"
    access_expires = datetime.fromisoformat(payload["access_expires_at"])
    refresh_expires = datetime.fromisoformat(payload["refresh_expires_at"])
    access_delta = (access_expires - datetime.utcnow()).total_seconds()
    refresh_delta = (refresh_expires - datetime.utcnow()).total_seconds()
    assert access_delta > 0
    assert refresh_delta > access_delta
    assert access_delta == pytest.approx(timedelta(minutes=15).total_seconds(), rel=0.05)


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(
    client: AsyncClient, dummy_user_service: DummyUserService
) -> None:
    dummy_user_service.create_user(email="charlie@example.com", password="topsecret")

    response = await client.post(
        "/api/auth/login",
        json={"email": "charlie@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


@pytest.mark.asyncio
async def test_crypto_endpoint_uses_primary_provider(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_crypto_service(monkeypatch)
    crypto_service = market_service.crypto_service
    provider_calls: List[str] = []

    async def fake_get_price(symbol: str) -> Optional[float]:
        provider_calls.append("coingecko")
        return 45000.0

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)
    binance_mock = AsyncMock(return_value={"price": "45100", "source": "Binance"})
    monkeypatch.setattr(market_service, "get_binance_price", binance_mock)

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        monkeypatch.setattr(alt_module.market_service.crypto_service, "get_price", fake_get_price)
        monkeypatch.setattr(alt_module.market_service, "get_binance_price", binance_mock)

    response = await client.get("/api/markets/crypto/btc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == 45000.0
    assert payload["source"] == "CryptoService + Binance"
    assert provider_calls == ["coingecko"]
    assert binance_mock.await_count == 1


@pytest.mark.asyncio
async def test_crypto_endpoint_falls_back_to_coinmarketcap(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_crypto_service(monkeypatch)
    crypto_service = market_service.crypto_service
    provider_calls: List[str] = []

    async def fake_get_price(symbol: str) -> Optional[float]:
        provider_calls.extend(["coingecko", "binance", "coinmarketcap"])
        return 123.45

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)
    monkeypatch.setattr(
        market_service,
        "get_binance_price",
        AsyncMock(return_value={"price": "123.40", "source": "Binance"}),
    )

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        monkeypatch.setattr(alt_module.market_service.crypto_service, "get_price", fake_get_price)
        monkeypatch.setattr(
            alt_module.market_service,
            "get_binance_price",
            AsyncMock(return_value={"price": "123.40", "source": "Binance"}),
        )

    response = await client.get("/api/markets/crypto/eth")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == 123.45
    assert payload["source"] == "CryptoService + Binance"
    assert provider_calls == ["coingecko", "binance", "coinmarketcap"]


@pytest.mark.asyncio
async def test_crypto_endpoint_returns_404_when_no_data(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_crypto_service(monkeypatch)
    crypto_service = market_service.crypto_service

    async def fake_get_price(symbol: str) -> Optional[float]:
        return None

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)
    monkeypatch.setattr(market_service, "get_binance_price", AsyncMock(return_value=None))

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        monkeypatch.setattr(alt_module.market_service.crypto_service, "get_price", fake_get_price)
        monkeypatch.setattr(alt_module.market_service, "get_binance_price", AsyncMock(return_value=None))

    response = await client.get("/api/markets/crypto/xrp")
    assert response.status_code == 404
    assert "No se encontró información" in response.json()["detail"]


@pytest.mark.asyncio
async def test_stock_endpoint_uses_fallback_provider(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _prepare_stock_service(monkeypatch)

    response = await client.get("/api/markets/stock/AAPL")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == pytest.approx(123.45)
    assert payload["source"] == "Yahoo Finance"
    assert info["calls"] == ["Alpha Vantage", "Twelve Data", "Yahoo Finance"]


@pytest.mark.asyncio
async def test_forex_endpoint_falls_back_to_yahoo(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _prepare_forex_service(monkeypatch)

    response = await client.get("/api/markets/forex/EURUSD")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == pytest.approx(1.2345)
    assert payload["source"] == "Yahoo Finance"
    assert info["calls"] == ["Twelve Data", "Yahoo Finance"]


@pytest.mark.asyncio
async def test_news_endpoints_use_fallbacks(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    info = _prepare_news_service(monkeypatch)
    monkeypatch.setattr(news_service_module.Config, "CRYPTOPANIC_API_KEY", "token")
    monkeypatch.setattr(news_service_module.Config, "NEWSAPI_API_KEY", "token")
    monkeypatch.setattr(news_service_module.Config, "FINFEED_API_KEY", "token")
    monkeypatch.setattr(news_service, "cache", DummyAsyncCache())

    crypto_response = await client.get("/api/news/crypto")
    assert crypto_response.status_code == 200
    crypto_payload = crypto_response.json()
    assert crypto_payload["category"] == "crypto"
    assert len(crypto_payload["articles"]) == 1

    finance_response = await client.get("/api/news/finance")
    assert finance_response.status_code == 200
    finance_payload = finance_response.json()
    assert finance_payload["category"] == "finance"
    assert len(finance_payload["articles"]) == 1

    assert info["calls"] == ["_fetch_cryptopanic", "_fetch_newsapi", "_fetch_finfeed"]


@pytest.mark.asyncio
async def test_alert_workflow_triggers_notification(
    client: AsyncClient,
    dummy_user_service: DummyUserService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register = await client.post(
        "/api/auth/register",
        json={"email": "alert@example.com", "password": "alerts1"},
    )
    assert register.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": "alert@example.com", "password": "alerts1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/api/alerts",
        json={"asset": "AAPL", "value": 120.0, "condition": "=="},
        headers=headers,
    )
    assert response.status_code == 201
    created_payload = response.json()
    assert created_payload["condition"] == "=="
    assert "updated_at" in created_payload
    assert created_payload["updated_at"]

    user_id = uuid.UUID(register.json()["id"])
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

    await alert_service.evaluate_alerts()

    assert notifications and notifications[0]["price"] == 120.0
    assert notifications[0]["alert"].id == created_alert.id


@pytest.mark.asyncio
async def test_alerts_list_returns_created_alert(
    client: AsyncClient,
    dummy_user_service: DummyUserService,
) -> None:
    register = await client.post(
        "/api/auth/register",
        json={"email": "list@example.com", "password": "alerts1"},
    )
    assert register.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": "list@example.com", "password": "alerts1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post(
        "/api/alerts",
        json={"asset": "ETH", "value": 1500.0, "condition": "<"},
        headers=headers,
    )
    assert create.status_code == 201
    created_alert = create.json()
    assert "updated_at" in created_alert
    assert created_alert["updated_at"]

    listing = await client.get("/api/alerts", headers=headers)
    assert listing.status_code == 200
    alerts = listing.json()
    assert len(alerts) == 1
    assert alerts[0]["asset"] == "ETH"
    assert alerts[0]["condition"] == "<"
    assert "updated_at" in alerts[0]
    assert alerts[0]["updated_at"]
