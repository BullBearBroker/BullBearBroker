from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest

from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def configure_ai_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mistral")
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "test-token", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_MODEL", "test/model", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config,
        "HUGGINGFACE_API_URL",
        "https://example.com/api",
        raising=False,
    )
    monkeypatch.setattr(
        ai_service_module.Config, "OLLAMA_HOST", "http://localhost:11434", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config, "OLLAMA_MODEL", "mock-ollama", raising=False
    )


@pytest.mark.anyio
async def test_process_message_uses_mocked_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    mistral_mock = AsyncMock(return_value="respuesta simulada")
    ollama_mock = AsyncMock(side_effect=AssertionError("Ollama no debería ejecutarse"))

    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False
    )
    monkeypatch.setattr(AIService, "process_with_mistral", mistral_mock)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_mock)

    result = await service.process_message("Dame un resumen del mercado")

    assert result.text == "respuesta simulada"
    assert result.provider == "mistral"
    assert mistral_mock.await_count == 1
    ollama_mock.assert_not_called()


@pytest.mark.anyio
async def test_call_with_backoff_falls_back_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    primary = AsyncMock(side_effect=TimeoutError("timeout"))
    secondary = AsyncMock(return_value="respuesta secundaria")
    sleep_mock = AsyncMock()

    monkeypatch.setattr(ai_service_module.asyncio, "sleep", sleep_mock)

    result, provider = await service._call_with_backoff(
        [
            ("primario", lambda: primary()),
            ("secundario", lambda: secondary()),
        ]
    )

    assert result == "respuesta secundaria"
    assert provider == "secundario"
    assert primary.await_count == 3
    assert secondary.await_count == 1
    assert sleep_mock.await_count == 2


@pytest.mark.anyio
async def test_call_with_backoff_raises_on_empty_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    failing_provider = AsyncMock(return_value="   ")
    sleep_mock = AsyncMock()

    monkeypatch.setattr(ai_service_module.asyncio, "sleep", sleep_mock)

    with pytest.raises(ValueError):
        await service._call_with_backoff([("mock", lambda: failing_provider())])

    assert failing_provider.await_count == 3
    assert sleep_mock.await_count == 2


class _DummyResponse:
    def __init__(self, status: int, json_data, text_data: str = "") -> None:
        self.status = status
        self._json_data = json_data
        self._text_data = text_data or ""

    async def __aenter__(self) -> _DummyResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data

    async def text(self) -> str:
        return self._text_data


class _DummySession:
    def __init__(self, response_factory: Callable[[], _DummyResponse]) -> None:
        self._response_factory = response_factory

    async def __aenter__(self) -> _DummySession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, *args, **kwargs) -> _DummyResponse:
        return self._response_factory()


@pytest.mark.anyio
async def test_huggingface_invalid_payload_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    def _response_factory() -> _DummyResponse:
        return _DummyResponse(status=200, json_data=[{}], text_data="{}")

    monkeypatch.setattr(
        ai_service_module.aiohttp,
        "ClientSession",
        lambda: _DummySession(_response_factory),
    )

    with pytest.raises(ValueError):
        await service._call_huggingface("", {})
