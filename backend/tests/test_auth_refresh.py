import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.security import decode_refresh
from backend.database import SessionLocal
from backend.main import app
from backend.models.refresh_token import RefreshToken


@pytest.mark.asyncio
async def test_rate_limit_health():
    ok_count = 0
    too_many = 0
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
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
    # Generar email único para cada ejecución del test
    unique_email = f"refresh_{uuid.uuid4().hex}@test.com"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Registrar usuario nuevo
        register = await client.post(
            "/api/auth/register",
            json={"email": unique_email, "password": "refresh123"},
        )
        assert register.status_code in (200, 201), register.text

        # 2. Login para obtener tokens
        login = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "refresh123"},
        )
        assert login.status_code == 200, login.text
        tokens = login.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        refresh_token = tokens["refresh_token"]

        with SessionLocal() as db:
            stored = (
                db.query(RefreshToken).filter(RefreshToken.token == refresh_token).one()
            )
            assert stored.expires_at is not None
            expected_exp = datetime.fromtimestamp(
                decode_refresh(refresh_token)["exp"], tz=UTC
            )
            if stored.expires_at.tzinfo is None:
                assert stored.expires_at == expected_exp.replace(tzinfo=None)
            else:
                assert stored.expires_at == expected_exp

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


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token():
    unique_email = f"logout_{uuid.uuid4().hex}@test.com"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        register = await client.post(
            "/api/auth/register",
            json={"email": unique_email, "password": "logout123"},
        )
        assert register.status_code in (200, 201), register.text

        login = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "logout123"},
        )
        assert login.status_code == 200, login.text
        refresh_token = login.json()["refresh_token"]

        with SessionLocal() as db:
            stored = (
                db.query(RefreshToken).filter(RefreshToken.token == refresh_token).one()
            )
            assert stored is not None

        logout = await client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout.status_code in (200, 204), logout.text

        with SessionLocal() as db:
            assert (
                db.query(RefreshToken)
                .filter(RefreshToken.token == refresh_token)
                .first()
            ) is None

        reuse = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_logout_revoke_all_refresh_tokens():
    unique_email = f"logout_all_{uuid.uuid4().hex}@test.com"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        register = await client.post(
            "/api/auth/register",
            json={"email": unique_email, "password": "logout123"},
        )
        assert register.status_code in (200, 201), register.text

        first_login = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "logout123"},
        )
        assert first_login.status_code == 200, first_login.text
        first_refresh = first_login.json()["refresh_token"]

        second_login = await client.post(
            "/api/auth/login",
            json={"email": unique_email, "password": "logout123"},
        )
        assert second_login.status_code == 200, second_login.text
        second_refresh = second_login.json()["refresh_token"]

        decoded = decode_refresh(second_refresh)
        user_id = uuid.UUID(decoded["sub"])

        with SessionLocal() as db:
            tokens = (
                db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()
            )
            assert len(tokens) >= 2

        logout_all = await client.post(
            "/api/auth/logout",
            json={"refresh_token": second_refresh, "revoke_all": True},
        )
        assert logout_all.status_code == 200, logout_all.text

        with SessionLocal() as db:
            remaining = (
                db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()
            )
            assert remaining == []

        reuse_first = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": first_refresh},
        )
        assert reuse_first.status_code == 401
