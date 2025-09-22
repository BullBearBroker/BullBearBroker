import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "backend"))

from backend.services.ai_service import AIService  # noqa: E402
from backend.services.huggingface_service import huggingface_service  # noqa: E402
from backend.services.mistral_service import mistral_service  # noqa: E402


@pytest.fixture(autouse=True)
def restore_providers():
    original_mistral_key = getattr(mistral_service, "api_key", None)
    original_hf_key = huggingface_service.api_key
    yield
    mistral_service.api_key = original_mistral_key
    huggingface_service.configure(original_hf_key)


def run_async(coro):
    return asyncio.run(coro)


def test_huggingface_fallback_after_mistral_failures(monkeypatch, caplog):
    service = AIService()
    mistral_service.api_key = "test-key"
    huggingface_service.configure("hf-token")

    monkeypatch.setattr(
        "backend.services.ai_service.asyncio.sleep", AsyncMock(), raising=False
    )
    monkeypatch.setattr(service, "_is_ollama_available", AsyncMock(return_value=False))

    mistral_mock = AsyncMock(side_effect=[RuntimeError("mistral down")] * service.max_retries)
    monkeypatch.setattr(service, "process_with_mistral", mistral_mock)

    huggingface_mock = AsyncMock(return_value="respuesta hf")
    monkeypatch.setattr(service, "_process_with_huggingface", huggingface_mock)

    caplog.set_level(logging.INFO)
    result = run_async(service.process_message("Hola"))

    assert result == "respuesta hf"
    assert mistral_mock.await_count == service.max_retries
    assert huggingface_mock.await_count == 1
    assert "huggingface" in caplog.text.lower()


def test_local_fallback_after_all_providers_fail(monkeypatch, caplog):
    service = AIService()
    mistral_service.api_key = "test-key"
    huggingface_service.configure("hf-token")

    monkeypatch.setattr(
        "backend.services.ai_service.asyncio.sleep", AsyncMock(), raising=False
    )
    monkeypatch.setattr(service, "_is_ollama_available", AsyncMock(return_value=True))

    mistral_mock = AsyncMock(side_effect=[RuntimeError("mistral down")] * service.max_retries)
    huggingface_mock = AsyncMock(side_effect=[RuntimeError("hf down")] * service.max_retries)
    ollama_mock = AsyncMock(side_effect=[RuntimeError("ollama down")] * service.max_retries)

    monkeypatch.setattr(service, "process_with_mistral", mistral_mock)
    monkeypatch.setattr(service, "_process_with_huggingface", huggingface_mock)
    monkeypatch.setattr(service, "_process_with_ollama", ollama_mock)

    fallback_mock = AsyncMock(return_value="fallback local")
    monkeypatch.setattr(service, "generate_response", fallback_mock)

    caplog.set_level(logging.ERROR)
    result = run_async(service.process_message("Consulta"))

    assert result == "fallback local"
    assert mistral_mock.await_count == service.max_retries
    assert huggingface_mock.await_count == service.max_retries
    assert ollama_mock.await_count == service.max_retries
    assert fallback_mock.await_count == 1
    assert "todos los proveedores fallaron" in caplog.text.lower()
