import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
def test_user():
    return {"email": "test@bullbear.ai", "password": "Test1234!"}


@pytest.mark.asyncio
async def test_auth_flow(test_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1) LOGIN
        resp = await client.post("/api/auth/login", json=test_user)
        assert resp.status_code == 200, resp.text
        login_data = resp.json()
        access_token = login_data["access_token"]
        r1 = login_data["refresh_token"]

        # 2) REFRESH (R1 -> R2)
        resp = await client.post("/api/auth/refresh", json={"refresh_token": r1})
        assert resp.status_code == 200, resp.text
        refresh_data = resp.json()
        r2 = refresh_data["refresh_token"]

        # 3) Reusar R1 (debe fallar con 401)
        resp = await client.post("/api/auth/refresh", json={"refresh_token": r1})
        assert resp.status_code == 401

        # 4) /auth/me con ACCESS
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 200, resp.text
        me_data = resp.json()
        assert me_data["email"] == test_user["email"]

        # 5) LOGOUT con R2
        resp = await client.post("/api/auth/logout", json={"refresh_token": r2})
        assert resp.status_code in (200, 204), resp.text

        # 6) Intentar refresh con R2 (ya revocado)
        resp = await client.post("/api/auth/refresh", json={"refresh_token": r2})
        assert resp.status_code == 401
