from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")
os.environ.setdefault("TESTING", "1")

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app
from backend.database import get_db
from backend.routers import auth as auth_router
from backend.tests.test_api_endpoints import DummyUserService as BaseUserService


class AuthDummyUserService(BaseUserService):
    def revoke_refresh_token(self, token: str) -> None:
        self._refresh_tokens.pop(token, None)

    def revoke_all_refresh_tokens(self, user_id: uuid.UUID) -> None:
        for key, entry in list(self._refresh_tokens.items()):
            if getattr(entry, "user_id", None) == user_id:
                self._refresh_tokens.pop(key, None)

    def ensure_user(self, email: str, password: str) -> None:
        if self.get_user_by_email(email) is None:
            self.create_user(email=email, password=password)


@pytest.fixture()
def in_memory_user_service(monkeypatch: pytest.MonkeyPatch) -> AuthDummyUserService:
    service = AuthDummyUserService()
    monkeypatch.setattr(auth_router, "user_service", service)
    monkeypatch.setattr("backend.main.user_service", service)
    monkeypatch.setattr(auth_router, "UserAlreadyExistsError", service.UserAlreadyExistsError)
    monkeypatch.setattr(auth_router, "InvalidCredentialsError", service.InvalidCredentialsError)
    monkeypatch.setattr(auth_router, "InvalidTokenError", service.InvalidTokenError)

    app.dependency_overrides[get_db] = lambda: None

    yield service

    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture()
async def client(in_memory_user_service: AuthDummyUserService) -> AsyncClient:  # type: ignore[name-defined]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_login_with_invalid_credentials_remains_unauthorized(client: AsyncClient) -> None:
    email = f"resilience_{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Valid123"},
    )
    assert register.status_code in (200, 201)

    for _ in range(2):
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "WrongPass"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]


@pytest.mark.asyncio
async def test_login_third_invalid_triggers_backoff(client: AsyncClient) -> None:
    email = f"backoff_{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Valid123"},
    )
    assert register.status_code in (200, 201)

    for attempt in range(2):
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "WrongPass"},
        )
        assert response.status_code == 401, f"Attempt {attempt + 1} should not be rate limited"

    third = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPass"},
    )
    assert third.status_code == 429
    assert third.json()["detail"]


@pytest.mark.asyncio
async def test_login_success_resets_backoff_state(client: AsyncClient) -> None:
    email = f"reset_{uuid.uuid4().hex}@example.com"
    password = "Valid123"
    register = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code in (200, 201)

    for attempt in range(2):
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "WrongPass"},
        )
        assert response.status_code == 401, f"Attempt {attempt + 1} should not be rate limited"

    success = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert success.status_code == 200

    post_reset = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPass"},
    )
    assert post_reset.status_code == 401
    assert post_reset.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_with_corrupted_token_returns_unauthorized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": "this-is-not-valid"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_unknown_token_is_handled(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/logout",
        json={"refresh_token": "missing-token"},
    )
    assert response.status_code in (200, 204)
    payload = response.json()
    assert payload.get("detail") in {"Session revoked", "All sessions revoked"}


@pytest.mark.asyncio
async def test_revoke_all_refresh_tokens_invalidates_existing_ones(client: AsyncClient) -> None:
    email = f"resilience_all_{uuid.uuid4().hex}@example.com"
    password = "Valid123"
    register = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code in (200, 201)

    first_login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert first_login.status_code == 200
    first_refresh = first_login.json()["refresh_token"]

    second_login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert second_login.status_code == 200
    second_refresh = second_login.json()["refresh_token"]

    logout_all = await client.post(
        "/api/auth/logout",
        json={"refresh_token": second_refresh, "revoke_all": True},
    )
    assert logout_all.status_code == 200

    reuse_first = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert reuse_first.status_code == 401

    reuse_second = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": second_refresh},
    )
    assert reuse_second.status_code == 401
