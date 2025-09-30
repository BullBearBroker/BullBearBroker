from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app
from backend.routers import health as health_module


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module.FastAPILimiter, "redis", None, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"health-{uuid.uuid4()}", 80)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "env" in body


@pytest.mark.asyncio
async def test_health_endpoint_returns_503_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenRedis:
        async def ping(self) -> None:
            raise RuntimeError("redis offline")

    broken = BrokenRedis()
    monkeypatch.setattr(health_module.FastAPILimiter, "redis", broken, raising=False)

    class FakeRateLimiter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __call__(self, request, response):
            try:
                await health_module.FastAPILimiter.redis.ping()
            except Exception as exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=503, detail="redis unavailable") from exc

    monkeypatch.setattr(health_module, "RateLimiter", FakeRateLimiter)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"health-fail-{uuid.uuid4()}", 80)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "redis unavailable"
