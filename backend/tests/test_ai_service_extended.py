import asyncio
from typing import Any, Dict

import pytest
from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


class _DummyResponse:
    def __init__(self, status: int, payload: Any):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def json(self) -> Any:
        return self._payload

    async def text(self) -> str:
        return ""


class _DummySession:
    def __init__(self, response: _DummyResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def post(self, *_args, **_kwargs) -> _DummyResponse:
        return self._response


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def configure_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_API_KEY", "token", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_MODEL", "base/model", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_API_URL", "https://example.com/models", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "OLLAMA_HOST", "http://localhost:11434", raising=False)
    monkeypatch.setattr(ai_service_module.Config, "OLLAMA_MODEL", "ollama-test", raising=False)


@pytest.fixture
def service() -> AIService:
    return AIService()


def test_select_model_for_risk_profile(service: AIService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_service_module.Config,
        "HUGGINGFACE_RISK_MODELS",
        {
            "investor": "model/investor",
            "trader": "model/trader",
            "analyst": "model/analyst",
            "fund": "model/fund",
        },
        raising=False,
    )

    assert service._select_model_for_profile("Investor") == "model/investor"
    assert service._select_model_for_profile("trader") == "model/trader"
    assert service._select_model_for_profile("ANALYST") == "model/analyst"
    assert service._select_model_for_profile("fund") == "model/fund"
    assert service._select_model_for_profile("unknown") == "base/model"


def test_build_prompt_rejects_empty_message(service: AIService) -> None:
    with pytest.raises(ValueError):
        service._build_prompt("   ", {})


@pytest.mark.anyio
async def test_huggingface_timeout_triggers_ollama(service: AIService, monkeypatch: pytest.MonkeyPatch) -> None:
    async def mistral_timeout(self, message: str, context: Dict[str, Any]) -> str:
        raise asyncio.TimeoutError("timeout")

    async def huggingface_timeout(self, message: str, context: Dict[str, Any]) -> str:
        raise asyncio.TimeoutError("timeout")

    async def ollama_success(self, message: str, context: Dict[str, Any]) -> str:
        return "respuesta ollama"

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(AIService, "process_with_mistral", mistral_timeout)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_timeout)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_success)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("Analiza ETH")
    assert result.provider == "ollama"
    assert "respuesta ollama" in result.text


@pytest.mark.anyio
async def test_huggingface_corrupt_json_raises(monkeypatch: pytest.MonkeyPatch, service: AIService) -> None:
    dummy_response = _DummyResponse(status=200, payload={"unexpected": "payload"})
    monkeypatch.setattr(
        ai_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(dummy_response),
    )

    with pytest.raises(ValueError):
        await service._call_huggingface("Mensaje", {"risk_profile": "investor"})


@pytest.mark.anyio
async def test_process_message_supports_streaming_mock(service: AIService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False)

    async def mistral_failure(self, message: str, context: Dict[str, Any]) -> str:
        raise RuntimeError("mistral down")

    async def streaming_ollama(self, message: str, context: Dict[str, Any]) -> str:
        async def _token_stream():
            for chunk in ("Hola", " mundo"):
                yield chunk

        collected = []
        async for token in _token_stream():
            collected.append(token)
        return "".join(collected)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(AIService, "process_with_mistral", mistral_failure)
    monkeypatch.setattr(AIService, "_call_ollama", streaming_ollama)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("Dame señales")
    assert result.provider == "ollama"
    assert result.text == "Hola mundo"
