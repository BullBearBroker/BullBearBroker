"""Pruebas de resiliencia para el caché inteligente del servicio IA."""

from unittest.mock import AsyncMock  # ✅ Codex fix: soporte de mocks async

import pytest

from backend.metrics.ai_metrics import (  # ✅ Codex fix: métricas cacheadas en tests
    ai_cache_hit_total,
    ai_cache_miss_total,
    ai_fallbacks_total,
)
from backend.services import ai_service as ai_service_module
from backend.services.ai_service import (  # ✅ Codex fix: utilidades de caché
    AIService,
    store_response_in_cache,
)
from backend.utils.config import Config


def _prepare_service_for_tests(
    service: AIService, monkeypatch: pytest.MonkeyPatch
) -> None:  # ✅ Codex fix: aislamiento de dependencias
    monkeypatch.setattr(service, "get_market_context", AsyncMock(return_value={}))
    monkeypatch.setattr(
        service, "_collect_indicator_snapshots", AsyncMock(return_value={})
    )
    monkeypatch.setattr(service, "_collect_news_highlights", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service, "_collect_alert_suggestions", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(service, "_collect_forex_quotes", AsyncMock(return_value=[]))


@pytest.mark.asyncio
async def test_ai_cache_hit_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validar que se registran hits y misses y se evita repetir llamadas."""

    service = AIService()
    cache = ai_service_module.cache
    if getattr(cache, "backend", "") == "memory":  # ✅ Codex fix: aislamiento memoria
        cache.client.clear()

    monkeypatch.setattr(Config, "HUGGINGFACE_API_KEY", None, raising=False)
    monkeypatch.setattr(Config, "OLLAMA_HOST", "http://localhost:11434", raising=False)

    mistral_mock = AsyncMock(return_value="Respuesta analítica primaria")
    monkeypatch.setattr(service, "process_with_mistral", mistral_mock)
    monkeypatch.setattr(service, "_call_ollama", AsyncMock(return_value="Ollama"))
    _prepare_service_for_tests(service, monkeypatch)

    message = "Analiza el precio de BTC"  # ✅ Codex fix: mensaje de prueba

    miss_before = ai_cache_miss_total.labels(model="mistral")._value.get()
    hit_before = ai_cache_hit_total.labels(model="mistral")._value.get()

    first_response = await service.process_message(message)
    second_response = await service.process_message(message)

    assert (
        mistral_mock.await_count == 1
    )  # ✅ Codex fix: el proveedor solo se invoca una vez
    assert first_response.text == second_response.text

    miss_after = ai_cache_miss_total.labels(model="mistral")._value.get()
    hit_after = ai_cache_hit_total.labels(model="mistral")._value.get()

    assert miss_after == miss_before + 1  # ✅ Codex fix: primer acceso registra miss
    assert hit_after == hit_before + 1  # ✅ Codex fix: segundo acceso registra hit


def test_store_response_in_cache_dynamic_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verificar que el TTL cambia dinámicamente según el tamaño del prompt."""

    recorded: dict[str, object] = {}

    def fake_set(key, value, ex=None):  # ✅ Codex fix: captura de parámetros TTL
        recorded["key"] = key
        recorded["value"] = value
        recorded["ex"] = ex

    monkeypatch.setattr(ai_service_module.cache, "set", fake_set)

    long_prompt = "x" * 501
    store_response_in_cache(
        "mistral", long_prompt, {"text": "ok", "provider": "mistral"}
    )

    assert recorded["ex"] == 600  # ✅ Codex fix: prompts largos usan TTL extendido
    assert recorded["key"].startswith("ai:mistral:")


@pytest.mark.asyncio
async def test_ai_cache_fallback_on_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garantizar fallback al caché cuando el proveedor falle."""

    service = AIService()
    cache = ai_service_module.cache
    if getattr(cache, "backend", "") == "memory":  # ✅ Codex fix: limpiar memoria
        cache.client.clear()

    monkeypatch.setattr(Config, "HUGGINGFACE_API_KEY", None, raising=False)
    monkeypatch.setattr(Config, "OLLAMA_HOST", "http://localhost:11434", raising=False)

    mistral_mock = AsyncMock(return_value="Respuesta inicial de Mistral")
    monkeypatch.setattr(service, "process_with_mistral", mistral_mock)
    monkeypatch.setattr(service, "_call_ollama", AsyncMock(return_value="Ollama"))
    _prepare_service_for_tests(service, monkeypatch)

    base_message = "Actualiza las perspectivas del EURUSD"  # ✅ Codex fix: prompt base
    first_payload = await service.process_message(base_message)
    assert "Respuesta inicial" in first_payload.text

    service._last_provider_attempted = "mistral"
    fail_mock = AsyncMock(side_effect=RuntimeError("provider fail"))
    monkeypatch.setattr(service, "_call_with_backoff", fail_mock)
    local_fallback = AsyncMock(return_value="Fallback local")
    monkeypatch.setattr(service, "generate_response", local_fallback)

    before_cache_fallback = ai_fallbacks_total.labels(
        from_provider="mistral", to_provider="cache"
    )._value.get()

    cached_result = await service.process_message(base_message)

    assert (
        cached_result.text == first_payload.text
    )  # ✅ Codex fix: se reutiliza la respuesta
    assert (
        local_fallback.await_count == 0
    )  # ✅ Codex fix: no se recurre al fallback local

    after_cache_fallback = ai_fallbacks_total.labels(
        from_provider="mistral", to_provider="cache"
    )._value.get()

    assert after_cache_fallback == before_cache_fallback + 1
