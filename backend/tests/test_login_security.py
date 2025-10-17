import asyncio
import hashlib
import time

import pytest

# QA: marcamos este módulo como rate_limit por validaciones de timings reales
pytestmark = pytest.mark.rate_limit
from httpx import ASGITransport, AsyncClient

from backend.core.login_backoff import login_backoff
from backend.main import app
from backend.services.user_service import user_service
from backend.utils.config import Config


@pytest.fixture(autouse=True)
async def _reset_backoff():
    # Ensure backoff state does not leak between tests
    yield
    await login_backoff.clear(hashlib.sha256(b"captcha@test.com").hexdigest()[:8])
    await login_backoff.clear(hashlib.sha256(b"rate@test.com").hexdigest()[:8])
    await login_backoff.clear(hashlib.sha256(b"existing@test.com").hexdigest()[:8])


@pytest.mark.asyncio
async def test_invalid_login_responses_are_consistent(monkeypatch):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        user_service.ensure_user("existing@test.com", "ValidPass123!")

        start_missing = time.perf_counter()
        resp_missing = await client.post(
            "/api/auth/login",
            json={"email": "missing@test.com", "password": "whatever123"},
        )
        duration_missing = time.perf_counter() - start_missing
        assert resp_missing.status_code == 401
        detail_missing = resp_missing.json()["detail"]

        start_wrong = time.perf_counter()
        resp_wrong = await client.post(
            "/api/auth/login",
            json={"email": "existing@test.com", "password": "wrongpass"},
        )
        duration_wrong = time.perf_counter() - start_wrong
        assert resp_wrong.status_code == 401
        detail_wrong = resp_wrong.json()["detail"]

        assert detail_missing == detail_wrong
        assert abs(duration_missing - duration_wrong) <= 0.3

    await login_backoff.clear(hashlib.sha256(b"existing@test.com").hexdigest()[:8])


@pytest.mark.asyncio
async def test_progressive_backoff(monkeypatch):
    monkeypatch.setattr(
        "backend.core.login_backoff.BACKOFF_WINDOWS",
        [0.2, 0.4, 0.6, 0.6],
        raising=False,
    )
    user_service.ensure_user("rate@test.com", "ValidPass123!")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp1 = await client.post(
            "/api/auth/login",
            json={"email": "rate@test.com", "password": "wrongpass"},
        )
        assert resp1.status_code == 401

        resp2 = await client.post(
            "/api/auth/login",
            json={"email": "rate@test.com", "password": "wrongpass"},
        )
        assert resp2.status_code == 429
        assert resp2.headers.get("Retry-After") == "1"

        await asyncio.sleep(0.25)
        resp3 = await client.post(
            "/api/auth/login",
            json={"email": "rate@test.com", "password": "wrongpass"},
        )
        assert resp3.status_code == 401

        resp4 = await client.post(
            "/api/auth/login",
            json={"email": "rate@test.com", "password": "wrongpass"},
        )
        assert resp4.status_code == 429
        assert resp4.headers.get("Retry-After") == "1"

    await login_backoff.clear(hashlib.sha256(b"rate@test.com").hexdigest()[:8])


@pytest.mark.asyncio
async def test_captcha_required_when_flag_enabled(monkeypatch):
    monkeypatch.setattr(Config, "ENABLE_CAPTCHA_ON_LOGIN", True, raising=False)
    monkeypatch.setattr(Config, "LOGIN_CAPTCHA_THRESHOLD", 1, raising=False)
    monkeypatch.setattr(
        Config, "LOGIN_CAPTCHA_TEST_SECRET", "captcha-ok", raising=False
    )
    monkeypatch.setattr(
        "backend.core.login_backoff.BACKOFF_WINDOWS",
        [0.1, 0.1, 0.1, 0.1],
        raising=False,
    )

    user_service.ensure_user("captcha@test.com", "ValidPass123!")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/auth/login",
            json={"email": "captcha@test.com", "password": "wrongpass"},
        )
        await asyncio.sleep(0.12)

        resp_without_captcha = await client.post(
            "/api/auth/login",
            json={"email": "captcha@test.com", "password": "ValidPass123!"},
        )
        assert resp_without_captcha.status_code == 403
        assert "verificación" in resp_without_captcha.json()["detail"].lower()

        resp_with_captcha = await client.post(
            "/api/auth/login",
            json={
                "email": "captcha@test.com",
                "password": "ValidPass123!",
                "captcha_token": "captcha-ok",
            },
        )
        assert resp_with_captcha.status_code == 200

    await login_backoff.clear(hashlib.sha256(b"captcha@test.com").hexdigest()[:8])
