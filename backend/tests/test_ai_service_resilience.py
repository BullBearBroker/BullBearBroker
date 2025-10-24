from unittest.mock import AsyncMock

import pytest
from prometheus_client import CollectorRegistry, Counter

from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


@pytest.fixture
def anyio_backend() -> str:  # pragma: no cover - required by anyio plugin
    return "asyncio"


@pytest.fixture(autouse=True)
def configure_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mistral")
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "token", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_MODEL", "test/model", raising=False
    )
    monkeypatch.setattr(
        ai_service_module.Config,
        "HUGGINGFACE_API_URL",
        "https://example.com",
        raising=False,
    )
    monkeypatch.setattr(
        ai_service_module.Config, "OLLAMA_HOST", "http://ollama", raising=False
    )
    monkeypatch.setattr(ai_service_module.Config, "OLLAMA_MODEL", "mock", raising=False)


@pytest.mark.parametrize("message", ["", None])
def test_build_prompt_rejects_empty_input(message):
    service = AIService()
    with pytest.raises(ValueError):
        service._build_prompt(message, {})  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_timeout_on_primary_provider_falls_back_to_huggingface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    sleep_mock = AsyncMock()
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", sleep_mock)

    mistral = AsyncMock(side_effect=TimeoutError("timeout"))
    huggingface = AsyncMock(return_value="respuesta huggingface")
    ollama = AsyncMock(return_value="respuesta ollama")

    monkeypatch.setattr(AIService, "get_market_context", AsyncMock(return_value={}))
    monkeypatch.setattr(
        AIService, "_collect_indicator_snapshots", AsyncMock(return_value={})
    )
    monkeypatch.setattr(
        AIService, "_collect_news_highlights", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        AIService, "_collect_alert_suggestions", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(AIService, "_collect_forex_quotes", AsyncMock(return_value=[]))

    monkeypatch.setattr(AIService, "process_with_mistral", mistral)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface)
    monkeypatch.setattr(AIService, "_call_ollama", ollama)

    result = await service.process_message("Precio BTC por favor")

    assert result.provider == "huggingface"
    assert "huggingface" in result.text
    assert mistral.await_count == 3  # tres reintentos antes del fallback
    assert huggingface.await_count == 1
    ollama.assert_not_awaited()
    assert sleep_mock.await_count == 2


@pytest.mark.anyio
async def test_corrupted_responses_trigger_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False
    )

    sleep_mock = AsyncMock()
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", sleep_mock)

    mistral = AsyncMock(return_value="   ")
    ollama = AsyncMock(return_value="")
    local_fallback = AsyncMock(return_value="respuesta local")

    monkeypatch.setattr(AIService, "get_market_context", AsyncMock(return_value={}))
    monkeypatch.setattr(
        AIService, "_collect_indicator_snapshots", AsyncMock(return_value={})
    )
    monkeypatch.setattr(
        AIService, "_collect_news_highlights", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        AIService, "_collect_alert_suggestions", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(AIService, "_collect_forex_quotes", AsyncMock(return_value=[]))

    monkeypatch.setattr(AIService, "process_with_mistral", mistral)
    monkeypatch.setattr(AIService, "_call_ollama", ollama)
    monkeypatch.setattr(AIService, "generate_response", local_fallback)

    result = await service.process_message("Dame contexto del mercado")

    assert result.provider == "local"
    assert result.text == "respuesta local"
    assert mistral.await_count == 3
    assert ollama.await_count == 3
    assert sleep_mock.await_count == 6
    local_fallback.assert_awaited_once()


@pytest.mark.anyio
async def test_long_prompt_triggers_cascade_to_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    sleep_mock = AsyncMock()
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", sleep_mock)

    long_message = "BTC " * 5000

    mistral = AsyncMock(side_effect=ValueError("prompt demasiado largo"))
    huggingface = AsyncMock(side_effect=ValueError("json inválido"))
    ollama = AsyncMock(return_value="respuesta ollama definitiva")

    monkeypatch.setattr(AIService, "get_market_context", AsyncMock(return_value={}))
    monkeypatch.setattr(
        AIService, "_collect_indicator_snapshots", AsyncMock(return_value={})
    )
    monkeypatch.setattr(
        AIService, "_collect_news_highlights", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        AIService, "_collect_alert_suggestions", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(AIService, "_collect_forex_quotes", AsyncMock(return_value=[]))

    monkeypatch.setattr(AIService, "process_with_mistral", mistral)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface)
    monkeypatch.setattr(AIService, "_call_ollama", ollama)

    result = await service.process_message(long_message)

    assert result.provider == "ollama"
    assert result.text.endswith("respuesta ollama definitiva")
    assert mistral.await_count == 3
    assert huggingface.await_count == 3
    ollama.assert_awaited_once()
    assert sleep_mock.await_count == 4


@pytest.mark.anyio
async def test_ai_service_records_failover_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AIService()

    registry = CollectorRegistry()
    counter = Counter(
        "ai_provider_failover_total",
        "Total AI provider failovers.",
        ["provider"],
        registry=registry,
    )
    monkeypatch.setattr(ai_service_module, "AI_PROVIDER_FAILOVER_TOTAL", counter)

    async def _fail(_providers):  # noqa: ANN001 - match internal signature
        raise RuntimeError("all providers unavailable")

    monkeypatch.setattr(service, "_call_with_backoff", _fail)
    monkeypatch.setattr(
        service, "generate_response", AsyncMock(return_value="fallback")
    )

    result = await service.process_message("hola", {})

    assert result.provider == "local"
    assert counter.labels(provider="local")._value.get() == pytest.approx(1.0)
