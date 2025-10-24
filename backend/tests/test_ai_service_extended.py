from json import JSONDecodeError
from typing import Any
from unittest.mock import AsyncMock

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
    monkeypatch.setenv("AI_PROVIDER", "mistral")
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
def service() -> AIService:
    return AIService()


def test_select_model_for_risk_profile(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
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
async def test_huggingface_timeout_triggers_ollama(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def mistral_timeout(self, message: str, context: dict[str, Any]) -> str:
        raise TimeoutError("timeout")

    async def huggingface_timeout(self, message: str, context: dict[str, Any]) -> str:
        raise TimeoutError("timeout")

    async def ollama_success(self, message: str, context: dict[str, Any]) -> str:
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
async def test_huggingface_corrupt_json_raises(
    monkeypatch: pytest.MonkeyPatch, service: AIService
) -> None:
    dummy_response = _DummyResponse(status=200, payload={"unexpected": "payload"})
    monkeypatch.setattr(
        ai_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(dummy_response),
    )

    with pytest.raises(ValueError):
        await service._call_huggingface("Mensaje", {"risk_profile": "investor"})


@pytest.mark.anyio
async def test_process_message_supports_streaming_mock(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False
    )

    async def mistral_failure(self, message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("mistral down")

    async def streaming_ollama(self, message: str, context: dict[str, Any]) -> str:
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
    async def mistral_failure(message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("mistral indisponible")

    async def huggingface_failure(self, message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("huggingface indisponible")

    async def ollama_failure(self, message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("ollama indisponible")

    original_generate_response = AIService.generate_response

    async def fallback_response(self, message: str) -> str:
        await original_generate_response(self, message)
        return await AIService.get_fallback_response(self, message)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        ai_service_module.mistral_service,
        "generate_financial_response",
        mistral_failure,
    )
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
    async def mistral_invalid(message: str, context: dict[str, Any]) -> str:
        raise JSONDecodeError("invalid", "{", 0)

    async def huggingface_success(self, message: str, context: dict[str, Any]) -> str:
        return "salida huggingface"

    async def ollama_not_called(self, message: str, context: dict[str, Any]) -> str:
        raise AssertionError("Ollama no debería usarse cuando HuggingFace funciona")

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        ai_service_module.mistral_service,
        "generate_financial_response",
        mistral_invalid,
    )
    monkeypatch.setattr(AIService, "_call_huggingface", huggingface_success)
    monkeypatch.setattr(AIService, "_call_ollama", ollama_not_called)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)

    result = await service.process_message("analiza sectores defensivos")
    assert result.provider == "huggingface"
    assert result.text == "salida huggingface"


@pytest.mark.anyio
async def test_prompt_too_long_triggers_fallback(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_build_prompt = AIService._build_prompt

    async def mistral_failure(message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("mistral indisponible")

    def limited_build_prompt(self, message: str, context: dict[str, Any]) -> str:
        prompt = original_build_prompt(self, message, context)
        if len(message) > 120:
            raise ValueError("Prompt demasiado largo")
        return prompt

    async def huggingface_wrapper(self, message: str, context: dict[str, Any]) -> str:
        _ = self._build_prompt(message, context)
        return "respuesta corta"

    async def ollama_wrapper(self, message: str, context: dict[str, Any]) -> str:
        _ = self._build_prompt(message, context)
        return "respuesta corta"

    original_generate_response = AIService.generate_response

    async def fallback_response(self, message: str) -> str:
        await original_generate_response(self, message)
        return await AIService.get_fallback_response(self, message)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        ai_service_module.mistral_service,
        "generate_financial_response",
        mistral_failure,
    )
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
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False
    )

    def fake_analyze(self, message: str) -> dict[str, Any]:
        return {
            "symbols": ["BTC"],
            "interval": "1h",
            "need_indicators": True,
            "need_news": True,
            "need_alerts": True,
            "forex_pairs": ["EURUSD"],
            "use_market_data": True,
        }

    async def fake_market_context(self, message: str) -> dict[str, Any]:
        return {
            "market_data": {
                "BTC": {
                    "raw_price": 45000.0,
                    "raw_change": 5.2,
                    "source": "TestFeed",
                }
            }
        }

    async def fake_indicators(self, message: str) -> dict[str, Any]:
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
        return [
            {"title": "BTC en alza", "source": "Daily", "url": "http://example.com"}
        ]

    async def fake_alerts(self, symbols: list, interval: str) -> list:
        return [{"symbol": "BTC", "suggestion": "Colocar stop", "notes": "Volatilidad"}]

    async def fake_forex(self, pairs: list) -> list:
        return ["EUR/USD: 1.1000 (+0.0100) — TestFX"]

    async def mistral_success(self, message: str, context: dict[str, Any]) -> str:
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


@pytest.mark.anyio
async def test_process_message_long_prompt_uses_local_fallback(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def timeout_mistral(message: str, context: dict[str, Any]) -> str:
        raise TimeoutError("mistral timeout")

    def rejecting_prompt(self, message: str, context: dict[str, Any]) -> str:
        if len(message) > 120:
            raise ValueError("prompt demasiado largo")
        return "prompt"

    async def failing_huggingface(self, message: str, context: dict[str, Any]) -> str:
        self._build_prompt(message, context)
        raise RuntimeError("huggingface rejected prompt")

    async def failing_ollama(self, message: str, context: dict[str, Any]) -> str:
        self._build_prompt(message, context)
        raise RuntimeError("ollama rejected prompt")

    async def blank_market_context(_self, _message: str) -> dict[str, Any]:
        return {}

    async def no_indicators(_self, _message: str) -> dict[str, Any]:
        return {}

    async def no_news(_self, _symbols: list) -> list:
        return []

    async def no_alerts(_self, _symbols: list, _interval: str) -> list:
        return []

    async def no_forex(_self, _pairs: list) -> list:
        return []

    async def controlled_local(self, message: str) -> str:
        return await AIService.get_fallback_response(self, message)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        ai_service_module.mistral_service,
        "generate_financial_response",
        timeout_mistral,
    )
    monkeypatch.setattr(AIService, "_build_prompt", rejecting_prompt)
    monkeypatch.setattr(AIService, "_call_huggingface", failing_huggingface)
    monkeypatch.setattr(AIService, "_call_ollama", failing_ollama)
    monkeypatch.setattr(AIService, "get_market_context", blank_market_context)
    monkeypatch.setattr(AIService, "_collect_indicator_snapshots", no_indicators)
    monkeypatch.setattr(AIService, "_collect_news_highlights", no_news)
    monkeypatch.setattr(AIService, "_collect_alert_suggestions", no_alerts)
    monkeypatch.setattr(AIService, "_collect_forex_quotes", no_forex)
    monkeypatch.setattr(AIService, "generate_response", controlled_local)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "token", raising=False
    )

    result = await service.process_message("x" * 200)

    assert result.provider == "local"
    assert "dificultades técnicas" in result.text.lower()


@pytest.mark.anyio
async def test_process_message_streaming_partial_accumulates_text(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def blank_market_context(_self, _message: str) -> dict[str, Any]:
        return {}

    async def no_indicators(_self, _message: str) -> dict[str, Any]:
        return {}

    async def no_news(_self, _symbols: list) -> list:
        return []

    async def no_alerts(_self, _symbols: list, _interval: str) -> list:
        return []

    async def no_forex(_self, _pairs: list) -> list:
        return []

    async def fake_backoff(self, providers):  # noqa: ANN001
        provider_name, _callable = providers[-1]
        collected = []

        async def _stream_tokens() -> None:
            for chunk in ("Hola", " mundo"):
                collected.append(chunk)

        await _stream_tokens()
        return "".join(collected), provider_name

    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "", raising=False
    )
    monkeypatch.setattr(AIService, "get_market_context", blank_market_context)
    monkeypatch.setattr(AIService, "_collect_indicator_snapshots", no_indicators)
    monkeypatch.setattr(AIService, "_collect_news_highlights", no_news)
    monkeypatch.setattr(AIService, "_collect_alert_suggestions", no_alerts)
    monkeypatch.setattr(AIService, "_collect_forex_quotes", no_forex)
    monkeypatch.setattr(AIService, "_call_with_backoff", fake_backoff)

    result = await service.process_message("resumen simple")

    assert result.provider == "ollama"
    assert result.text.strip().endswith("Hola mundo")


@pytest.mark.anyio
async def test_process_message_cascading_failures_trigger_fallback(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def timeout_mistral(message: str, context: dict[str, Any]) -> str:
        raise TimeoutError("timeout mistral")

    async def corrupt_huggingface(self, message: str, context: dict[str, Any]) -> str:
        raise JSONDecodeError("corrupt", "{}", 0)

    async def failing_ollama(self, message: str, context: dict[str, Any]) -> str:
        raise RuntimeError("ollama failure")

    async def blank_market_context(_self, _message: str) -> dict[str, Any]:
        return {}

    async def no_indicators(_self, _message: str) -> dict[str, Any]:
        return {}

    async def no_news(_self, _symbols: list) -> list:
        return []

    async def no_alerts(_self, _symbols: list, _interval: str) -> list:
        return []

    async def no_forex(_self, _pairs: list) -> list:
        return []

    async def fallback_response(self, message: str) -> str:
        return await AIService.get_fallback_response(self, message)

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        ai_service_module.mistral_service,
        "generate_financial_response",
        timeout_mistral,
    )
    monkeypatch.setattr(AIService, "_call_huggingface", corrupt_huggingface)
    monkeypatch.setattr(AIService, "_call_ollama", failing_ollama)
    monkeypatch.setattr(AIService, "get_market_context", blank_market_context)
    monkeypatch.setattr(AIService, "_collect_indicator_snapshots", no_indicators)
    monkeypatch.setattr(AIService, "_collect_news_highlights", no_news)
    monkeypatch.setattr(AIService, "_collect_alert_suggestions", no_alerts)
    monkeypatch.setattr(AIService, "_collect_forex_quotes", no_forex)
    monkeypatch.setattr(AIService, "generate_response", fallback_response)
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        ai_service_module.Config, "HUGGINGFACE_API_KEY", "token", raising=False
    )

    result = await service.process_message("Analiza el SP500")

    assert result.provider == "local"
    assert "dificultades técnicas" in result.text.lower()


def test_summarize_market_context_formats_output(service: AIService) -> None:
    context = {
        "market_data": {
            "BTC": {
                "raw_price": 45000.1234,
                "raw_change": 2.5,
                "source": "Feed",
            },
            "ETH": {
                "price": "2000",  # fallback path when raw_price missing
                "change": "1.2%",
            },
        }
    }

    lines = service._summarize_market_context(context)

    assert lines[0].startswith("BTC: precio 45,000.12")
    assert "ETH" in lines[1]


def test_summarize_indicators_includes_available_metrics(service: AIService) -> None:
    indicator_map = {
        "BTC": {
            "interval": "1h",
            "indicators": {
                "rsi": {"value": 55.2},
                "macd": {"macd": 0.12345},
                "atr": {"value": 1.234},
                "stochastic_rsi": {"%K": 80.0},
                "vwap": {"value": 23000.987},
            },
        }
    }

    lines = service._summarize_indicators(indicator_map)

    assert "RSI 55.2" in lines[0]
    assert "MACD 0.123" in lines[0]
    assert "ATR 1.234" in lines[0]
    assert "StochRSI %K 80.0" in lines[0]
    assert "VWAP 23000.987" in lines[0]


@pytest.mark.anyio
async def test_collect_forex_quotes_formats_pairs(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _ForexStub:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def get_quote(self, pair: str) -> dict[str, Any]:
            self.calls.append(pair)
            return {"price": 1.2345, "change": 0.0021, "source": "Stub"}

    forex_stub = _ForexStub()
    monkeypatch.setattr(ai_service_module, "forex_service", forex_stub)

    quotes = await service._collect_forex_quotes(["EURUSD", "GBP/USD"])

    assert forex_stub.calls == ["EURUSD", "GBP/USD"]
    assert quotes[0].startswith("EUR/USD")
    assert "Stub" in quotes[0]


@pytest.mark.anyio
async def test_call_with_backoff_retries_until_success(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = {"count": 0}

    async def provider_failure_then_success() -> str:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("fail once")
        return "ok"

    sleep_mock = AsyncMock()
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", sleep_mock)

    result, provider = await service._call_with_backoff(
        [("custom", provider_failure_then_success)]
    )

    assert result == "ok"
    assert provider == "custom"
    assert attempts["count"] == 2
    sleep_mock.assert_awaited()
