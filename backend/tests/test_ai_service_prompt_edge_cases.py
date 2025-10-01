import asyncio
from unittest.mock import AsyncMock
from typing import Any, Dict

import pytest

from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


@pytest.fixture(autouse=True)
def configure_ai_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_API_KEY", "token", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_MODEL", "base/model", raising=False)
    monkeypatch.setattr(
        ai_service_module.Config,
        "HUGGINGFACE_RISK_MODELS",
        {"conservador": "hf/conservative", "agresivo": "hf/aggressive"},
        raising=False,
    )
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_API_URL", "https://example.com/models", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "OLLAMA_HOST", "http://localhost:11434", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "OLLAMA_MODEL", "ollama-test", raising=False)


@pytest.fixture
def service() -> AIService:
    return AIService()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_build_prompt_rejects_empty_message(service: AIService) -> None:
    with pytest.raises(ValueError):
        service._build_prompt("", {})


def test_build_prompt_accepts_large_messages(service: AIService) -> None:
    long_message = "Analiza " + "BTC " * 1024

    prompt = service._build_prompt(long_message, {})

    assert "BTC" in prompt
    assert len(prompt) > len(long_message)


@pytest.mark.anyio
async def test_process_message_empty_prompt_triggers_local_fallback(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mistral_failure(message: str, context: Dict[str, Any]) -> str:  # noqa: ARG001
        raise RuntimeError("provider down")

    async def huggingface_failure(self, message: str, context: Dict[str, Any]) -> str:  # noqa: ARG001
        raise ValueError("json decode error")

    async def ollama_failure(self, message: str, context: Dict[str, Any]) -> str:  # noqa: ARG001
        raise asyncio.TimeoutError("ollama timeout")

    monkeypatch.setattr(AIService, "process_with_mistral", mistral_failure)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_failure)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_failure)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", AsyncMock(return_value=None))

    result = await service.process_message("")

    assert result.provider == "local"
    assert "BullBearBroker" in result.text


@pytest.mark.anyio
async def test_call_huggingface_raises_for_unexpected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIService()

    class DummyResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        async def json(self):  # noqa: D401
            return "not-json"

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        def post(self, *args, **kwargs):  # noqa: D401
            return DummyResponse()

    monkeypatch.setattr(ai_service_module.aiohttp, "ClientSession", lambda: DummySession())

    with pytest.raises(ValueError):
        await service._call_huggingface("mensaje", {"risk_profile": "agresivo"})


@pytest.mark.anyio
async def test_model_selection_uses_risk_profile_mapping(service: AIService) -> None:
    class DummyResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        async def json(self):  # noqa: D401
            return [{"generated_text": "respuesta"}]

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        def post(self, *args, **kwargs):  # noqa: D401
            return DummyResponse()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(ai_service_module.aiohttp, "ClientSession", lambda: DummySession())

    payload = await service._call_huggingface("hola", {"risk_profile": "agresivo"})

    assert payload == "respuesta"

    monkeypatch.undo()


@pytest.mark.anyio
async def test_call_with_backoff_tracks_invalid_provider(service: AIService, monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: Dict[str, int] = {"invalid": 0}

    async def failing_provider() -> str:
        attempts["invalid"] += 1
        raise ValueError("bad provider response")

    monkeypatch.setattr(ai_service_module.asyncio, "sleep", AsyncMock(return_value=None))

    with pytest.raises(ValueError):
        await service._call_with_backoff([("invalid", failing_provider)])

    assert attempts["invalid"] == 3
