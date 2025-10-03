from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.core.rate_limit import reset_rate_limiter_cache  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers import health as health_module  # noqa: E402


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_rate_limiter_cache("health_endpoint")
    monkeypatch.setattr(health_module.FastAPILimiter, "redis", None, raising=False)

    async def _fake_db_check() -> dict[str, str]:
        return {"status": "ok"}

    monkeypatch.setattr(health_module, "_check_database", _fake_db_check)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"health-{uuid.uuid4()}", 80)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "env" in body
    assert body["services"]["redis"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_health_endpoint_returns_503_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_rate_limiter_cache("health_endpoint")

    class BrokenRedis:
        async def ping(self) -> None:
            raise RuntimeError("redis offline")

    broken = BrokenRedis()
    monkeypatch.setattr(health_module.FastAPILimiter, "redis", broken, raising=False)

    async def _fake_db_check() -> dict[str, str]:
        return {"status": "ok"}

    monkeypatch.setattr(health_module, "_check_database", _fake_db_check)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"health-fail-{uuid.uuid4()}", 80)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["services"]["redis"]["status"] == "error"


@pytest.mark.asyncio
async def test_health_endpoint_reports_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_rate_limiter_cache("health_endpoint")

    async def _failing_db_check() -> dict[str, str]:
        await asyncio.sleep(0)
        return {"status": "error", "detail": "db offline"}

    monkeypatch.setattr(health_module, "_check_database", _failing_db_check)
    monkeypatch.setattr(health_module.FastAPILimiter, "redis", None, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"health-db-{uuid.uuid4()}", 80)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["services"]["database"]["status"] == "error"
