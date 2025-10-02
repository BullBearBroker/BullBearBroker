from pathlib import Path
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.password_guard import configure_password_detector
from backend.utils.config import Config


@pytest.mark.asyncio
async def test_registration_rejects_compromised_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = tmp_path / "compromised.txt"
    dataset.write_text("leaked-pass\nsha1hash\n")

    monkeypatch.setattr(Config, "ENABLE_PASSWORD_BREACH_CHECK", True, raising=False)
    monkeypatch.setattr(Config, "PASSWORD_BREACH_DATASET_PATH", str(dataset), raising=False)
    configure_password_detector(str(dataset))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        bad_response = await client.post(
            "/api/auth/register",
            json={"email": "breach@test.com", "password": "leaked-pass"},
        )
        assert bad_response.status_code == 400
        assert bad_response.json()["detail"] == "Credenciales inválidas"

        safe_email = f"safe-{uuid.uuid4().hex}@test.com"

        good_response = await client.post(
            "/api/auth/register",
            json={"email": safe_email, "password": "StrongPass!1"},
        )
        assert good_response.status_code == 201

    configure_password_detector(None)
