import asyncio
import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.login_backoff import login_backoff
from backend.main import app
from backend.services.user_service import user_service
from backend.utils.config import Config


@pytest.mark.asyncio
async def test_soft_lock_triggers_and_resets(monkeypatch: pytest.MonkeyPatch) -> None:
    email = "soft@test.com"
    password = "ValidPass123!"
    user_service.ensure_user(email, password)

    monkeypatch.setattr(Config, "LOGIN_SOFT_LOCK_THRESHOLD", 2, raising=False)
    monkeypatch.setattr(Config, "LOGIN_SOFT_LOCK_COOLDOWN", 1, raising=False)
    monkeypatch.setattr(Config, "ENABLE_CAPTCHA_ON_LOGIN", False, raising=False)
    monkeypatch.setattr("backend.routers.auth._SOFT_LOCK_THRESHOLD", 2, raising=False)
    monkeypatch.setattr("backend.routers.auth._SOFT_LOCK_COOLDOWN", 1, raising=False)
    monkeypatch.setattr("backend.routers.auth._LOGIN_BACKOFF_START_AFTER", 10, raising=False)

    events: list[dict] = []

    def _capture_event(logger, **payload):  # noqa: ANN001 - signature matches log_event
        events.append(payload)

    monkeypatch.setattr("backend.routers.auth.log_event", _capture_event)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for _ in range(2):
            response = await client.post(
                "/api/auth/login",
                json={"email": email, "password": "wrong"},
            )
            assert response.status_code == 401

        soft_lock_events = [evt for evt in events if evt.get("event") == "account_soft_lock"]
        assert soft_lock_events, "Soft lock event should be emitted"
        hashed_email = hashlib.sha256(email.encode("utf-8")).hexdigest()[:8]
        assert soft_lock_events[-1].get("email_hash") == hashed_email

        locked = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert locked.status_code == 423
        assert locked.headers.get("Retry-After") == "1"

        await asyncio.sleep(1.05)

        success = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert success.status_code == 200

    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()[:8]
    assert await login_backoff.failure_count(email_hash) == 0
    assert await login_backoff.cooldown_remaining_seconds(email_hash) == 0
    await login_backoff.clear(email_hash)
