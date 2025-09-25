import pytest
from httpx import AsyncClient, ASGITransport
from fastapi_limiter import FastAPILimiter

from backend.main import app


@pytest.mark.asyncio
async def test_app_lifespan_and_health():
    # ✅ limpiar rate limiter antes de ejecutar este test
    if FastAPILimiter.redis:
        await FastAPILimiter.redis.flushdb()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test del endpoint raíz
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        data = root_resp.json()
        assert "message" in data
        assert "BullBearBroker API" in data["message"]

        # Test del endpoint /api/health
        health_resp = await client.get("/api/health")
        if health_resp.status_code == 200:
            data = health_resp.json()
            assert "status" in data
            assert data["status"] == "ok"
        elif health_resp.status_code == 429:
            data = health_resp.json()
            assert "detail" in data
            assert data["detail"] == "Too Many Requests"
        else:
            pytest.fail(f"Respuesta inesperada: {health_resp.status_code}, {health_resp.json()}")
