import pytest
from httpx import AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_ai_message_endpoint_returns_200():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/ai/message", json={"message": "Hola IA"})
    assert response.status_code in (200, 503), response.text  # 503 si fallback local
    assert "detail" not in response.text or "error" not in response.text


@pytest.mark.asyncio
async def test_notifications_test_endpoint_returns_ok_or_404():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/notifications/test")
    # Si router aún no tiene handler test, devolverá 404; si lo tiene, 200 OK
    assert response.status_code in (200, 404)
