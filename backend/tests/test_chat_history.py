import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from backend.database import SessionLocal
from backend.main import app
from backend.models import ChatMessage
from backend.services.ai_service import AIResponsePayload, ai_service
from backend.utils.config import Config


@pytest.mark.asyncio
async def test_chat_persists_history(monkeypatch):
    monkeypatch.setattr(Config, "MISTRAL_API_KEY", "test-key", raising=False)

    async def fake_process(message: str, context: dict | None) -> AIResponsePayload:
        return AIResponsePayload(text=f"Respuesta a: {message}", provider="test", used_data=True, sources=["prices"])

    monkeypatch.setattr(ai_service, "process_message", fake_process)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"chat_{uuid.uuid4().hex}@test.com"
        register = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "chat1234"},
        )
        assert register.status_code in (200, 201)

        login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "chat1234"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        chat_response = await client.post(
            "/api/ai/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Hola"},
        )
        assert chat_response.status_code == 200, chat_response.text
        data = chat_response.json()
        session_id = uuid.UUID(data["session_id"])
        assert data["response"].startswith("Respuesta a")

        with SessionLocal() as db:
            rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
                .all()
            )
            assert len(rows) == 2
            assert [row.role for row in rows] == ["user", "assistant"]

        history = await client.get(
            f"/api/ai/history/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history.status_code == 200, history.text
        history_data = history.json()
        assert history_data["session_id"] == str(session_id)
        assert len(history_data["messages"]) == 2
        assert history_data["messages"][0]["role"] == "user"
        assert history_data["messages"][1]["role"] == "assistant"

        # Reuse session
        second = await client.post(
            "/api/ai/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Seguimos", "session_id": str(session_id)},
        )
        assert second.status_code == 200

        with SessionLocal() as db:
            total = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
                .all()
            )
            assert len(total) == 4


@pytest.mark.asyncio
async def test_history_requires_valid_session(monkeypatch):
    monkeypatch.setattr(Config, "MISTRAL_API_KEY", "test-key", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"history_{uuid.uuid4().hex}@test.com"
        await client.post(
            "/api/auth/register",
            json={"email": email, "password": "chat1234"},
        )
        login = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "chat1234"},
        )
        token = login.json()["access_token"]

        missing = await client.get(
            f"/api/ai/history/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert missing.status_code == 404
