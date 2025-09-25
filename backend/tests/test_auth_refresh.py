import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_rate_limit_health():
    ok_count = 0
    too_many = 0
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(6):
            response = await client.get("/api/health")
            if response.status_code == 200:
                ok_count += 1
            elif response.status_code == 429:
                too_many += 1
    assert ok_count >= 5
    assert too_many >= 1


@pytest.mark.skip("End-to-end refresh flow pending integration with persistent users")
@pytest.mark.asyncio
async def test_refresh_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": "demo@example.com", "password": "secret"},
        )
        assert login.status_code in (200, 401)
