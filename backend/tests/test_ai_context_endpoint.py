import importlib

import pytest
from httpx import AsyncClient

sentiment_module = importlib.import_module("backend.services.sentiment_service")
context_module = importlib.import_module("backend.services.context_service")


@pytest.mark.asyncio
async def test_ai_context_basic_flow(monkeypatch, async_client: AsyncClient):
    async def fake_process_message(self, message, context=None):
        class DummyResponse:
            text = "Respuesta simulada"
            provider = "test"

        return DummyResponse()

    monkeypatch.setattr(
        sentiment_module,
        "analyze_sentiment",
        lambda text: {"label": "positive", "score": 0.9},
    )
    monkeypatch.setattr(context_module, "get_history", lambda session_id: [])
    monkeypatch.setattr(context_module, "save_message", lambda *args, **kwargs: None)

    from backend.services.ai_service import ai_service

    monkeypatch.setattr(
        ai_service,
        "process_message",
        fake_process_message.__get__(ai_service, ai_service.__class__),
    )

    payload = {"session_id": "s1", "message": "El mercado está en alza"}
    response = await async_client.post("/api/ai/context", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Respuesta simulada"
    assert data["sentiment"]["label"] == "positive"
    assert data["history_len"] == 0


@pytest.mark.asyncio
async def test_ai_context_handles_sentiment_error(
    monkeypatch, async_client: AsyncClient
):
    monkeypatch.setattr(
        sentiment_module,
        "analyze_sentiment",
        lambda text: {"label": "unknown", "score": 0.0},
    )
    monkeypatch.setattr(context_module, "get_history", lambda session_id: [])
    monkeypatch.setattr(context_module, "save_message", lambda *args, **kwargs: None)

    from backend.services.ai_service import ai_service

    async def fake_process_message(self, message, context=None):
        class DummyResponse:
            text = "Otra respuesta"
            provider = "test"

        return DummyResponse()

    monkeypatch.setattr(
        ai_service,
        "process_message",
        fake_process_message.__get__(ai_service, ai_service.__class__),
    )

    payload = {"session_id": "error", "message": "Prueba de fallo"}
    response = await async_client.post("/api/ai/context", json=payload)
    assert response.status_code == 200
    assert response.json()["sentiment"]["label"] == "unknown"
