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


@pytest.mark.asyncio
async def test_refresh_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Registrar usuario nuevo
        register = await client.post(
            "/api/auth/register",
            json={"email": "refresh@test.com", "password": "refresh123"},
        )
        assert register.status_code in (200, 201), register.text

        # 2. Login para obtener tokens
        login = await client.post(
            "/api/auth/login",
            json={"email": "refresh@test.com", "password": "refresh123"},
        )
        assert login.status_code == 200, login.text
        tokens = login.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        refresh_token = tokens["refresh_token"]

        # 3. Usar refresh_token para obtener nuevo access_token
        refresh = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh.status_code == 200, refresh.text
        data2 = refresh.json()
        assert "access_token" in data2
        assert "refresh_token" in data2
        assert data2["refresh_token"] != refresh_token  # debe rotar
