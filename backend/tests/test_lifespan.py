import pytest
from httpx import AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_app_lifespan_and_health():
    # Cliente asíncrono que gestiona startup y shutdown automáticamente
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test del endpoint raíz
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        data = root_resp.json()
        assert "message" in data
        assert "BullBearBroker API" in data["message"]

        # Test del endpoint /api/health
        health_resp = await client.get("/api/health")
        assert health_resp.status_code == 200
        data = health_resp.json()
        assert data["status"] == "ok"   # 👈 validamos solo status
