import asyncio
from json import JSONDecodeError
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


def test_select_model_for_fund_profile_is_case_insensitive(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_service_module.Config,
        "HUGGINGFACE_RISK_MODELS",
        {"Fund": "model/smart-fund"},
        raising=False,
    )

    assert service._select_model_for_profile("Fund") == "model/smart-fund"
    assert service._select_model_for_profile("fund") == "model/smart-fund"


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


@pytest.mark.anyio
async def test_all_providers_failure_returns_controlled_message(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mistral_failure(message: str, context: Dict[str, Any]) -> str:
        raise RuntimeError("mistral indisponible")

    async def huggingface_failure(self, message: str, context: Dict[str, Any]) -> str:
        raise RuntimeError("huggingface indisponible")

    async def ollama_failure(self, message: str, context: Dict[str, Any]) -> str:
        raise RuntimeError("ollama indisponible")

    original_generate_response = AIService.generate_response

    async def fallback_response(self, message: str) -> str:
        await original_generate_response(self, message)
        return await AIService.get_fallback_response(self, message)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(ai_service_module.mistral_service, "generate_financial_response", mistral_failure)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_failure)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_failure)
    monkeypatch.setattr(AIService, "generate_response", fallback_response)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("escenario sin proveedores disponibles")
    assert result.provider == "local"
    assert "dificultades técnicas" in result.text.lower()


@pytest.mark.anyio
async def test_json_decode_error_from_mistral_uses_next_provider(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mistral_invalid(message: str, context: Dict[str, Any]) -> str:
        raise JSONDecodeError("invalid", "{", 0)

    async def huggingface_success(self, message: str, context: Dict[str, Any]) -> str:
        return "salida huggingface"

    async def ollama_not_called(self, message: str, context: Dict[str, Any]) -> str:
        raise AssertionError("Ollama no debería usarse cuando HuggingFace funciona")

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(ai_service_module.mistral_service, "generate_financial_response", mistral_invalid)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_success)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_not_called)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("analiza sectores defensivos")
    assert result.provider == "huggingface"
    assert result.text == "salida huggingface"


@pytest.mark.anyio
async def test_prompt_too_long_triggers_fallback(service: AIService, monkeypatch: pytest.MonkeyPatch) -> None:
    original_build_prompt = AIService._build_prompt
    async def mistral_failure(message: str, context: Dict[str, Any]) -> str:
        raise RuntimeError("mistral indisponible")

    def limited_build_prompt(self, message: str, context: Dict[str, Any]) -> str:
        prompt = original_build_prompt(self, message, context)
        if len(message) > 120:
            raise ValueError("Prompt demasiado largo")
        return prompt

    async def huggingface_wrapper(self, message: str, context: Dict[str, Any]) -> str:
        _ = self._build_prompt(message, context)
        return "respuesta corta"

    async def ollama_wrapper(self, message: str, context: Dict[str, Any]) -> str:
        _ = self._build_prompt(message, context)
        return "respuesta corta"

    original_generate_response = AIService.generate_response

    async def fallback_response(self, message: str) -> str:
        await original_generate_response(self, message)
        return await AIService.get_fallback_response(self, message)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(ai_service_module.mistral_service, "generate_financial_response", mistral_failure)
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_wrapper)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_wrapper)
    monkeypatch.setattr(AIService, "_build_prompt", limited_build_prompt)
    monkeypatch.setattr(AIService, "generate_response", fallback_response)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("x" * 200)
    assert result.provider == "local"
    assert "dificultades técnicas" in result.text.lower()


@pytest.mark.anyio
async def test_process_message_builds_enrichment_summary(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False)

    def fake_analyze(self, message: str) -> Dict[str, Any]:
        return {
            "symbols": ["BTC"],
            "interval": "1h",
            "need_indicators": True,
            "need_news": True,
            "need_alerts": True,
            "forex_pairs": ["EURUSD"],
            "use_market_data": True,
        }

    async def fake_market_context(self, message: str) -> Dict[str, Any]:
        return {
            "market_data": {
                "BTC": {
                    "raw_price": 45000.0,
                    "raw_change": 5.2,
                    "source": "TestFeed",
                }
            }
        }

    async def fake_indicators(self, message: str) -> Dict[str, Any]:
        return {
            "BTC": {
                "interval": "1h",
                "indicators": {
                    "rsi": {"value": 55.1},
                    "vwap": {"value": 123.45},
                },
            }
        }

    async def fake_news(self, symbols: list) -> list:
        return [{"title": "BTC en alza", "source": "Daily", "url": "http://example.com"}]

    async def fake_alerts(self, symbols: list, interval: str) -> list:
        return [{"symbol": "BTC", "suggestion": "Colocar stop", "notes": "Volatilidad"}]

    async def fake_forex(self, pairs: list) -> list:
        return ["EUR/USD: 1.1000 (+0.0100) — TestFX"]

    async def mistral_success(self, message: str, context: Dict[str, Any]) -> str:
        return "Respuesta principal Mistral"

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(AIService, "_analyze_message", fake_analyze)
    monkeypatch.setattr(AIService, "get_market_context", fake_market_context)
    monkeypatch.setattr(AIService, "_collect_indicator_snapshots", fake_indicators)
    monkeypatch.setattr(AIService, "_collect_news_highlights", fake_news)
    monkeypatch.setattr(AIService, "_collect_alert_suggestions", fake_alerts)
    monkeypatch.setattr(AIService, "_collect_forex_quotes", fake_forex)
    monkeypatch.setattr(AIService, "process_with_mistral", mistral_success)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("Analiza BTC con noticias y alertas")

    assert result.provider == "mistral"
    assert result.used_data is True
    assert set(result.sources) == {"prices", "indicators", "news", "alerts"}
    assert "📈 Datos de mercado" in result.text
    assert "📊 Indicadores técnicos" in result.text
    assert "📰 Noticias relevantes" in result.text
    assert "🚨 Ideas de alertas" in result.text
    assert "Respuesta principal Mistral" in result.text
