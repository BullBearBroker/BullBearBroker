"""Integration tests for the /alerts endpoints using an in-memory user service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app
from backend.routers import alerts as alerts_router
from backend.routers import auth as auth_router


@dataclass
class DummyAlert:
    """Lightweight alert entity mirroring the SQLAlchemy model attributes."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    asset: str
    value: float
    condition: str
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DummyUser:
    """Simple user representation with the fields required by the routers."""

    id: uuid.UUID
    email: str
    password: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def verify_password(self, password: str) -> bool:  # pragma: no cover - simple helper
        return self.password == password


class DummyUserService:
    """In-memory stand-in for the database-backed UserService."""

    class UserAlreadyExistsError(Exception):
        pass

    class UserNotFoundError(Exception):
        pass

    class InvalidCredentialsError(Exception):
        pass

    class InvalidTokenError(Exception):
        pass

    def __init__(self) -> None:
        self._users_by_email: Dict[str, DummyUser] = {}
        self._users_by_id: Dict[uuid.UUID, DummyUser] = {}
        self._alerts: Dict[uuid.UUID, List[DummyAlert]] = {}
        self._sessions: List[SimpleNamespace] = []
        self._refresh_tokens: Dict[str, SimpleNamespace] = {}
        self._secret = "test-secret"
        self._algorithm = "HS256"

    # ---------------------------
    # User helpers
    # ---------------------------
    def create_user(self, email: str, password: str) -> DummyUser:
        if email in self._users_by_email:
            raise self.UserAlreadyExistsError("Email ya está registrado")

        user = DummyUser(id=uuid.uuid4(), email=email, password=password)
        self._users_by_email[email] = user
        self._users_by_id[user.id] = user
        self._alerts[user.id] = []
        return user

    def get_user_by_email(self, email: str) -> Optional[DummyUser]:
        return self._users_by_email.get(email)

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
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover - deterministic expiry
            raise self.InvalidTokenError("Token expirado") from exc
        except jwt.InvalidTokenError as exc:
            raise self.InvalidTokenError("Token inválido") from exc

    @staticmethod
    def _extract_expiration(payload: Dict[str, Any]) -> datetime:
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
        except ValueError as exc:  # pragma: no cover - defensive
            raise DummyUserService.InvalidTokenError("Token inválido") from exc

    def create_access_token(
        self, user: DummyUser, expires_in: Optional[timedelta] = None
    ) -> Tuple[str, datetime]:
        expires_at = datetime.utcnow() + (expires_in or timedelta(minutes=15))
        payload = self._build_payload(user, expires_at)
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def create_session(
        self,
        user_id: uuid.UUID,
        token: Optional[str] = None,
        expires_in: Optional[timedelta] = None,
    ) -> Tuple[str, SimpleNamespace]:
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
            expires_at = self._extract_expiration(payload)

        session = SimpleNamespace(user_id=user_id, token=token, expires_at=expires_at)
        self._sessions.append(session)
        return token, session

    def create_refresh_token(
        self, user: DummyUser, expires_in: Optional[timedelta] = None
    ) -> Tuple[str, datetime]:
        refresh_token = jwt.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "exp": datetime.utcnow() + (expires_in or timedelta(days=7)),
            },
            self._secret,
            algorithm=self._algorithm,
        )
        expires_at = datetime.utcnow() + (expires_in or timedelta(days=7))
        self._refresh_tokens[refresh_token] = SimpleNamespace(
            user_id=user.id,
            expires_at=expires_at,
        )
        return refresh_token, expires_at

    def rotate_refresh_token(self, refresh_token: str) -> Tuple[DummyUser, str, datetime]:
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
    ) -> Tuple[str, datetime, str, datetime]:
        access_token, session = self.create_session(user.id)
        refresh_token, refresh_expires = self.create_refresh_token(user)
        return access_token, session.expires_at, refresh_token, refresh_expires

    def register_session_activity(self, token: str) -> None:  # pragma: no cover - unused
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

    # ---------------------------
    # Alert helpers
    # ---------------------------
    def create_alert(
        self,
        user_id: uuid.UUID,
        *,
        title: str,
        asset: str,
        value: float,
        condition: str,
        active: bool = True,
    ) -> DummyAlert:
        if user_id not in self._alerts:
            raise self.UserNotFoundError("Usuario no encontrado")

        alert = DummyAlert(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            asset=asset.upper(),
            value=value,
            condition=condition,
            active=active,
        )
        self._alerts[user_id].append(alert)
        return alert

    def get_alerts_for_user(self, user_id: uuid.UUID) -> List[DummyAlert]:
        return list(self._alerts.get(user_id, []))

    def delete_alert_for_user(self, user_id: uuid.UUID, alert_id: uuid.UUID) -> bool:
        alerts = self._alerts.get(user_id)
        if not alerts:
            return False
        for idx, alert in enumerate(alerts):
            if alert.id == alert_id:
                alerts.pop(idx)
                return True
        return False

    def update_alert(
        self,
        user_id: uuid.UUID,
        alert_id: uuid.UUID,
        *,
        title: Optional[str] = None,
        asset: Optional[str] = None,
        value: Optional[float] = None,
        condition: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> DummyAlert:
        alerts = self._alerts.get(user_id)
        if not alerts:
            raise self.UserNotFoundError("Alerta no encontrada para este usuario")

        for alert in alerts:
            if alert.id == alert_id:
                if title is not None:
                    alert.title = title
                if asset is not None:
                    alert.asset = asset.upper()
                if value is not None:
                    alert.value = value
                if condition is not None:
                    alert.condition = condition
                if active is not None:
                    alert.active = active
                alert.updated_at = datetime.utcnow()
                return alert

        raise self.UserNotFoundError("Alerta no encontrada para este usuario")

    def delete_all_alerts_for_user(self, user_id: uuid.UUID) -> int:
        alerts = self._alerts.get(user_id, [])
        count = len(alerts)
        self._alerts[user_id] = []
        return count


@pytest.fixture()
def dummy_user_service(monkeypatch: pytest.MonkeyPatch) -> DummyUserService:
    service = DummyUserService()

    monkeypatch.setattr(auth_router, "user_service", service)
    monkeypatch.setattr(alerts_router, "user_service", service)
    monkeypatch.setattr(auth_router, "UserAlreadyExistsError", service.UserAlreadyExistsError)
    monkeypatch.setattr(auth_router, "InvalidCredentialsError", service.InvalidCredentialsError)
    monkeypatch.setattr(alerts_router, "UserNotFoundError", service.UserNotFoundError)
    monkeypatch.setattr(auth_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "InvalidTokenError", service.InvalidTokenError)
    monkeypatch.setattr(alerts_router, "USER_SERVICE_ERROR", None)

    return service


@pytest_asyncio.fixture()
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _register_and_login(
    service: DummyUserService, email: str, password: str
) -> str:
    user = service.create_user(email=email, password=password)
    token, _ = service.create_session(user.id)
    return token


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_alert(client: AsyncClient, dummy_user_service: DummyUserService) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    payload = {
        "title": "Cruce AAPL",
        "asset": "aapl",
        "value": 150.0,
        "condition": ">",
        "active": True,
    }
    response = await client.post("/api/alerts", json=payload, headers=_auth_header(token))

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Cruce AAPL"
    assert body["asset"] == "AAPL"
    assert body["condition"] == ">"
    assert pytest.approx(body["value"], rel=1e-6) == 150.0
    assert body["active"] is True


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient, dummy_user_service: DummyUserService) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    payload = {
        "title": "BTC supera",
        "asset": "btc",
        "value": 42000.0,
        "condition": ">",
        "active": True,
    }
    await client.post("/api/alerts", json=payload, headers=_auth_header(token))

    response = await client.get("/api/alerts", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["title"] == "BTC supera"
    assert body[0]["asset"] == "BTC"
    assert body[0]["active"] is True


@pytest.mark.asyncio
async def test_update_alert(client: AsyncClient, dummy_user_service: DummyUserService) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    create_payload = {
        "title": "ETH objetivo",
        "asset": "eth",
        "value": 3000.0,
        "condition": ">",
        "active": True,
    }
    create_response = await client.post(
        "/api/alerts", json=create_payload, headers=_auth_header(token)
    )
    alert_id = create_response.json()["id"]

    update_payload = {
        "title": "ETH soporte",
        "asset": "eth",
        "value": 2950.0,
        "condition": "<",
        "active": False,
    }
    response = await client.put(
        f"/api/alerts/{alert_id}", json=update_payload, headers=_auth_header(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == alert_id
    assert body["title"] == "ETH soporte"
    assert body["condition"] == "<"
    assert pytest.approx(body["value"], rel=1e-6) == 2950.0
    assert body["active"] is False


@pytest.mark.asyncio
async def test_delete_alert(client: AsyncClient, dummy_user_service: DummyUserService) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    create_payload = {
        "title": "TSLA breakout",
        "asset": "tsla",
        "value": 250.0,
        "condition": ">",
        "active": True,
    }
    create_response = await client.post(
        "/api/alerts", json=create_payload, headers=_auth_header(token)
    )
    alert_id = create_response.json()["id"]

    response = await client.delete(f"/api/alerts/{alert_id}", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json() == {
        "message": "Alerta eliminada exitosamente",
        "id": alert_id,
    }

    list_response = await client.get("/api/alerts", headers=_auth_header(token))
    assert list_response.status_code == 200
    assert list_response.json() == []


@pytest.mark.asyncio
async def test_delete_all_alerts(client: AsyncClient, dummy_user_service: DummyUserService) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    payload = {
        "title": "MSFT retroceso",
        "asset": "msft",
        "value": 320.0,
        "condition": "<",
        "active": True,
    }
    await client.post("/api/alerts", json=payload, headers=_auth_header(token))
    await client.post("/api/alerts", json=payload, headers=_auth_header(token))

    response = await client.delete("/api/alerts", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json() == {
        "message": "Todas las alertas fueron eliminadas exitosamente",
    }

    list_response = await client.get("/api/alerts", headers=_auth_header(token))
    assert list_response.status_code == 200
    assert list_response.json() == []


@pytest.mark.asyncio
async def test_create_alert_with_invalid_payload_returns_422(
    client: AsyncClient, dummy_user_service: DummyUserService
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    invalid_payload = {
        "title": "",
        "asset": "btc",
        "value": "not-a-number",
        "condition": ">",
        "active": True,
    }

    response = await client.post(
        "/api/alerts", json=invalid_payload, headers=_auth_header(token)
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_alert_returns_404(
    client: AsyncClient, dummy_user_service: DummyUserService
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    response = await client.delete(
        f"/api/alerts/{uuid.uuid4()}", headers=_auth_header(token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_alerts_empty_returns_empty_list(
    client: AsyncClient, dummy_user_service: DummyUserService
) -> None:
    email = f"user-{uuid.uuid4()}@example.com"
    token = await _register_and_login(dummy_user_service, email, "secret123")

    response = await client.get("/api/alerts", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json() == []
