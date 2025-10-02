import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import HTTPException, Request
from starlette.responses import Response

from backend.core.rate_limit import reset_rate_limiter_cache
from backend.main import app
from backend.routers import alerts as alerts_router
from backend.routers import auth as auth_router


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limits() -> None:
    reset_rate_limiter_cache()
    yield
    reset_rate_limiter_cache()


class _StubUserService:
    def authenticate_user(self, *args, **kwargs):  # noqa: ANN001, D401 - simple stub
        raise auth_router.InvalidCredentialsError("Credenciales inválidas")


@pytest.mark.asyncio()
async def test_login_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_router, "user_service", _StubUserService())

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"auth-rate-{uuid.uuid4()}", 80)),
        base_url="http://testserver",
    ) as client:
        for _ in range(5):
            resp = await client.post(
                "/api/auth/login",
                json={"email": "user@example.com", "password": "invalid"},
            )
            assert resp.status_code == 401

        final = await client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "invalid"},
        )

    assert final.status_code == 429


@pytest.mark.asyncio()
async def test_alert_dispatch_rate_limit() -> None:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/alerts/send",
        "headers": [(b"host", b"testserver"), (b"authorization", b"bearer token")],
        "client": ("127.0.0.1", 9000),
        "scheme": "http",
        "server": ("testserver", 80),
    }
    request = Request(scope)
    response = Response()

    for _ in range(5):
        await alerts_router._dispatch_alert_rate_limit(request, response)

    with pytest.raises(HTTPException) as excinfo:
        await alerts_router._dispatch_alert_rate_limit(request, response)

    assert excinfo.value.status_code == 429
