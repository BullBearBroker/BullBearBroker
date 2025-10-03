import uuid
from pathlib import Path

DEFAULT_DB_PATH = Path("bullbearbroker.db")
if DEFAULT_DB_PATH.exists():
    DEFAULT_DB_PATH.unlink()

import pytest
from httpx import ASGITransport, AsyncClient
from pyotp import TOTP

from backend.core.security import decode_refresh
from backend.database import SessionLocal
from backend.main import app
from backend.models.refresh_token import RefreshToken


@pytest.mark.asyncio
async def test_login_without_mfa():
    email = f"auth_nomfa_{uuid.uuid4().hex}@test.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Password123"},
        )
        assert register.status_code in (200, 201), register.text

        login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert login.status_code == 200, login.text
        tokens = login.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_login_with_mfa_requires_code():
    email = f"auth_mfa_{uuid.uuid4().hex}@test.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Password123"},
        )
        assert register.status_code in (200, 201), register.text

        first_login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert first_login.status_code == 200, first_login.text
        tokens = first_login.json()

        setup = await client.post(
            "/api/auth/mfa/setup",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]

        verify_code = TOTP(secret).now()
        verify = await client.post(
            "/api/auth/mfa/verify",
            json={"code": verify_code},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert verify.status_code == 200, verify.text

        second_login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert second_login.status_code == 401
        assert second_login.json()["detail"] == "mfa_required"

        mfa_code = TOTP(secret).now()
        third_login = await client.post(
            "/api/auth/login",
            json={
                "email": email,
                "password": "Password123",
                "mfa_code": mfa_code,
            },
        )
        assert third_login.status_code == 200, third_login.text


@pytest.mark.asyncio
async def test_logout_all_revokes_tokens():
    email = f"auth_logoutall_{uuid.uuid4().hex}@test.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Password123"},
        )
        assert register.status_code in (200, 201), register.text

        first_login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert first_login.status_code == 200, first_login.text
        first_tokens = first_login.json()

        second_login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert second_login.status_code == 200, second_login.text
        second_tokens = second_login.json()

        decoded = decode_refresh(second_tokens["refresh_token"])
        user_id = uuid.UUID(decoded["sub"])

        with SessionLocal() as db:
            stored = (
                db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()
            )
            assert stored, "Expected refresh tokens stored for user"

        logout_all = await client.post(
            "/api/auth/logout_all",
            headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
        )
        assert logout_all.status_code == 200, logout_all.text

        with SessionLocal() as db:
            remaining = (
                db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()
            )
            assert remaining == []

        reuse = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": second_tokens["refresh_token"]},
        )
        assert reuse.status_code == 401
