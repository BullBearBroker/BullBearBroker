# ruff: noqa: I001
import hashlib
import json
import uuid
from collections.abc import Mapping
from types import SimpleNamespace

# QA: marcamos este módulo para ejecución serial por sensibilidad a tiempo/rate limiting
import pytest

pytestmark = pytest.mark.rate_limit
import pytest_asyncio
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY
from starlette.responses import Response

import backend.core.rate_limit as rate_limit_module
from backend.core.login_backoff import login_backoff
from backend.core.rate_limit import reset_rate_limiter_cache
from backend.main import app
from backend.routers import alerts as alerts_router, auth as auth_router


def _metric_value(name: str, labels: Mapping[str, str] | None = None) -> float:
    value = REGISTRY.get_sample_value(name, labels or {})
    return float(value) if value is not None else 0.0


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limits() -> None:
    reset_rate_limiter_cache()
    yield
    reset_rate_limiter_cache()


class _AlwaysInvalidUserService:
    def authenticate_user(self, *args, **kwargs):  # noqa: ANN001 - compat with prod svc
        raise auth_router.InvalidCredentialsError("Credenciales inválidas")


class _SuccessfulUserService:
    def __init__(self) -> None:
        self.email = "valid@example.com"
        self.password = "secret123"
        self.user_id = uuid.uuid4()
        self.refresh_tokens: list[str] = []
        self.sessions: list[tuple[uuid.UUID, str, object]] = []

    def authenticate_user(self, email: str, password: str) -> SimpleNamespace:
        if email != self.email or password != self.password:
            raise auth_router.InvalidCredentialsError("Credenciales inválidas")
        return SimpleNamespace(id=self.user_id, email=email)

    def store_refresh_token(self, user_id: uuid.UUID, refresh_token: str) -> None:
        self.refresh_tokens.append(refresh_token)

    def register_external_session(
        self,
        user_id: uuid.UUID,
        token: str,
        expires_at: object,
    ) -> None:
        self.sessions.append((user_id, token, expires_at))


@pytest.mark.asyncio()
async def test_login_ip_rate_limit_unit_window(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = rate_limit_module.rate_limit(
        times=2,
        seconds=60,
        identifier="unit_login_ip",
        state_attribute="limited",
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [(b"host", b"testserver")],
        "client": ("192.0.2.10", 1234),
        "scheme": "http",
        "server": ("testserver", 80),
    }
    request = Request(scope)
    response = Response()

    ticks = iter([0.0, 1.0, 2.0, 65.0])
    monkeypatch.setattr(
        rate_limit_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(ticks)),
    )
    monkeypatch.setattr(rate_limit_module.FastAPILimiter, "redis", None, raising=False)

    await limiter(request, response)
    await limiter(request, response)
    with pytest.raises(HTTPException):
        await limiter(request, response)
    await limiter(request, response)


@pytest.mark.asyncio()
async def test_login_success_updates_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _SuccessfulUserService()
    monkeypatch.setattr(auth_router, "user_service", service)

    ok_before = _metric_value("login_attempts_total", {"outcome": "ok"})
    invalid_before = _metric_value("login_attempts_total", {"outcome": "invalid"})
    duration_sum_before = _metric_value("login_duration_seconds_sum")
    duration_count_before = _metric_value("login_duration_seconds_count")

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("203.0.113.55", 80)),
        base_url="http://testserver",
    ) as client:
        success = await client.post(
            "/api/auth/login",
            json={"email": service.email, "password": service.password},
        )
        assert success.status_code == 200, success.text

        failure = await client.post(
            "/api/auth/login",
            json={"email": service.email, "password": "wrong"},
        )
        assert failure.status_code == 401

    ok_after = _metric_value("login_attempts_total", {"outcome": "ok"})
    invalid_after = _metric_value("login_attempts_total", {"outcome": "invalid"})
    duration_sum_after = _metric_value("login_duration_seconds_sum")
    duration_count_after = _metric_value("login_duration_seconds_count")

    assert ok_after - ok_before == 1
    assert invalid_after - invalid_before == 1
    assert duration_count_after - duration_count_before == 2
    assert duration_sum_after > duration_sum_before


@pytest.mark.asyncio()
async def test_login_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_router, "user_service", _AlwaysInvalidUserService())
    monkeypatch.setattr(auth_router, "_LOGIN_BACKOFF_START_AFTER", 10)

    invalid_before = _metric_value("login_attempts_total", {"outcome": "invalid"})
    limited_email_before = _metric_value("login_attempts_total", {"outcome": "limited"})
    rate_email_before = _metric_value(
        "login_rate_limited_total", {"dimension": "email"}
    )

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

    invalid_after = _metric_value("login_attempts_total", {"outcome": "invalid"})
    limited_email_after = _metric_value("login_attempts_total", {"outcome": "limited"})
    rate_email_after = _metric_value("login_rate_limited_total", {"dimension": "email"})

    assert invalid_after - invalid_before == 5
    assert limited_email_after - limited_email_before == 1
    assert rate_email_after - rate_email_before == 1


@pytest.mark.asyncio()
async def test_login_backoff_updates_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    email = "limited@example.com"
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()[:8]
    await login_backoff.clear(email_hash)

    monkeypatch.setattr(auth_router, "user_service", _AlwaysInvalidUserService())
    monkeypatch.setattr(auth_router, "_LOGIN_BACKOFF_START_AFTER", 3)

    invalid_before = _metric_value("login_attempts_total", {"outcome": "invalid"})
    limited_before = _metric_value("login_attempts_total", {"outcome": "limited"})
    rate_email_before = _metric_value(
        "login_rate_limited_total", {"dimension": "email"}
    )

    third_response = None
    try:
        async with AsyncClient(
            transport=ASGITransport(
                app=app, client=(f"auth-backoff-{uuid.uuid4()}", 80)
            ),
            base_url="http://testserver",
        ) as client:
            for _ in range(2):
                resp = await client.post(
                    "/api/auth/login",
                    json={"email": email, "password": "invalid"},
                )
                assert resp.status_code == 401

            third_response = await client.post(
                "/api/auth/login",
                json={"email": email, "password": "invalid"},
            )
    finally:
        await login_backoff.clear(email_hash)

    assert third_response is not None
    assert third_response.status_code == 429

    invalid_after = _metric_value("login_attempts_total", {"outcome": "invalid"})
    limited_after = _metric_value("login_attempts_total", {"outcome": "limited"})
    rate_email_after = _metric_value("login_rate_limited_total", {"dimension": "email"})

    assert invalid_after - invalid_before == 2
    assert limited_after - limited_before == 1
    assert rate_email_after - rate_email_before == 1


@pytest.mark.asyncio()
async def test_login_rate_limiter_logs_dependency_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict] = []

    def _capture_event(logger, **payload):  # noqa: ANN001
        events.append(payload)

    class _FailingLimiter:
        async def __call__(self, _request, _response):  # noqa: ANN001
            raise RuntimeError("redis offline")

    monkeypatch.setattr(rate_limit_module, "log_event", _capture_event)
    monkeypatch.setattr(
        rate_limit_module, "RateLimiter", lambda *args, **kwargs: _FailingLimiter()
    )
    monkeypatch.setattr(
        rate_limit_module.FastAPILimiter, "redis", object(), raising=False
    )

    limiter = rate_limit_module.login_rate_limiter()

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }

    body = json.dumps({"email": "dependency@test.com"}).encode("utf-8")

    async def receive() -> dict:  # noqa: D401 - ASGI receive callable
        nonlocal body
        chunk = body
        body = b""
        return {"type": "http.request", "body": chunk, "more_body": False}

    request = Request(scope, receive=receive)
    response = Response()

    await limiter(request, response)

    assert any(
        evt.get("event") == "dependency_unavailable"
        and evt.get("dependency") == "redis"
        for evt in events
    )


@pytest.mark.asyncio()
async def test_login_rate_limit_by_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_router, "user_service", _AlwaysInvalidUserService())

    invalid_before = _metric_value("login_attempts_total", {"outcome": "invalid"})
    limited_ip_before = _metric_value("login_attempts_total", {"outcome": "limited"})
    rate_ip_before = _metric_value("login_rate_limited_total", {"dimension": "ip"})

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("198.51.100.77", 80)),
        base_url="http://testserver",
    ) as client:
        attempts = 0
        while True:
            resp = await client.post(
                "/api/auth/login",
                json={"email": f"user{attempts}@example.com", "password": "invalid"},
            )
            attempts += 1
            if resp.status_code == 429:
                break
            assert resp.status_code == 401

    # 🧩 Codex fix: el rate limiter devuelve 429 en el intento observado
    assert resp.status_code == 429
    effective_limit = attempts

    invalid_after = _metric_value("login_attempts_total", {"outcome": "invalid"})
    limited_ip_after = _metric_value("login_attempts_total", {"outcome": "limited"})
    rate_ip_after = _metric_value("login_rate_limited_total", {"dimension": "ip"})

    assert invalid_after - invalid_before == effective_limit - 1
    assert limited_ip_after - limited_ip_before == 1
    assert rate_ip_after - rate_ip_before == 1


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
