from typing import Any

import pytest

from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


@pytest.fixture(autouse=True)
def configure_ai_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "token", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_MODEL", "base/model", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config,
        "HUGGINGFACE_API_URL",
        "https://example.com/models",
        raising=False,
    )
    monkeypatch.setattr(
        ai_service_module.Config, "OLLAMA_HOST", "http://localhost:11434", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config, "OLLAMA_MODEL", "ollama-test", raising=False
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def service() -> AIService:
    return AIService()


@pytest.mark.anyio
async def test_mistral_timeout_falls_back_to_huggingface(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mistral_timeout(self, message: str, context: dict[str, Any]) -> str:
        raise TimeoutError("timeout")

    async def huggingface_success(self, message: str, context: dict[str, Any]) -> str:
        return "respuesta desde huggingface"

    async def ollama_not_called(self, message: str, context: dict[str, Any]) -> str:
        raise AssertionError("Ollama no debería ejecutarse cuando HuggingFace responde")

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(AIService, "process_with_mistral", mistral_timeout)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_success)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_not_called)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("Analiza BTC")

    assert result.provider == "huggingface"
    assert "huggingface" in result.text


@pytest.mark.anyio
async def test_call_with_backoff_propagates_last_error(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_counts: dict[str, int] = {"primary": 0, "secondary": 0}

    async def failing_primary() -> str:
        call_counts["primary"] += 1
        raise TimeoutError("fuente primaria sin respuesta")

    async def failing_secondary() -> str:
        call_counts["secondary"] += 1
        raise ValueError("formato secundario inválido")

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(ValueError, match="formato secundario inválido"):
        await service._call_with_backoff(
            [
                ("primario", failing_primary),
                ("secundario", failing_secondary),
            ]
        )

    assert call_counts["primary"] == 3
    assert call_counts["secondary"] == 3
