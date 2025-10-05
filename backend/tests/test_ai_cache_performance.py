import asyncio
import logging
from typing import Any

import pytest

from backend.metrics.ai_metrics import ai_adaptive_timeouts_total
from backend.services.ai_service import AIService, PROVIDER_TIMEOUTS
from backend.services.cache_service import (
    AICacheService,
    ai_cache_hits_total,
    ai_cache_misses_total,
)


@pytest.mark.asyncio
async def test_process_message_cache_hit_and_miss(monkeypatch, caplog):
    service = AIService()

    async def fake_backoff(*args, **kwargs):
        return "respuesta generada", "mistral"

    monkeypatch.setattr(service, "_call_with_backoff", fake_backoff)
    service._ai_cache_service = AICacheService()

    hits_before = ai_cache_hits_total._value.get()
    misses_before = ai_cache_misses_total._value.get()

    caplog.set_level(logging.INFO)
    await service.process_message("Consulta de prueba")

    misses_after = ai_cache_misses_total._value.get()
    assert misses_after == pytest.approx(misses_before + 1)
    assert any("cache_miss" in record.message for record in caplog.records)

    caplog.clear()
    await service.process_message("Consulta de prueba")
    hits_after = ai_cache_hits_total._value.get()
    assert hits_after == pytest.approx(hits_before + 1)
    assert any("cache_hit" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_dynamic_ttl(monkeypatch):
    captured: list[tuple[str, int, int]] = []

    async def fake_get(self, route, prompt):
        return None

    async def fake_set(self, route, prompt, response, ttl):
        captured.append((route, ttl, len(prompt)))

    monkeypatch.setattr(AICacheService, "get", fake_get)
    monkeypatch.setattr(AICacheService, "set", fake_set)

    prompt_cycle = iter(["corto", "largo" * 40])

    def fake_build_prompt(self, message, context):
        return next(prompt_cycle)

    monkeypatch.setattr(AIService, "_build_prompt", fake_build_prompt)

    service = AIService()
    service.market_service = None

    async def fake_backoff(*args, **kwargs):
        return "respuesta corta", "mistral"

    monkeypatch.setattr(service, "_call_with_backoff", fake_backoff)
    service._ai_cache_service = AICacheService()

    await service.process_message("Breve consulta")
    assert captured
    assert captured[-1][1] == 3600

    captured.clear()

    long_message = "Detalles " + ("extendidos " * 5)
    await service.process_message(long_message)
    assert captured
    assert captured[-1][1] == 600


@pytest.mark.asyncio
async def test_deduplicated_prompts(monkeypatch):
    service = AIService()
    service._ai_cache_service = AICacheService()
    call_counter = 0

    async def fake_backoff(*args, **kwargs):
        nonlocal call_counter
        call_counter += 1
        await asyncio.sleep(0.01)
        return "respuesta deduplicada", "mistral"

    monkeypatch.setattr(service, "_call_with_backoff", fake_backoff)

    results = await asyncio.gather(
        service.process_message("Deduplicación"),
        service.process_message("Deduplicación"),
        service.process_message("Deduplicación"),
    )

    assert call_counter == 1
    assert all(result.text for result in results)


def test_adaptive_timeout_logging(monkeypatch, caplog):
    service = AIService()
    caplog.set_level(logging.WARNING)
    baseline = ai_adaptive_timeouts_total._value.get()
    previous_timeout = PROVIDER_TIMEOUTS["mistral"]
    service._latency_stats = {"Mistral": {"avg": 0.1, "count": 5.0}}

    try:
        service._handle_adaptive_timeout("mistral", "Mistral", 1.0, "sync")
        assert ai_adaptive_timeouts_total._value.get() == pytest.approx(
            baseline + 1
        )
        assert any("adaptive_timeout_triggered" in record.message for record in caplog.records)
        assert PROVIDER_TIMEOUTS["mistral"] >= max(previous_timeout, 1.5)
    finally:
        PROVIDER_TIMEOUTS["mistral"] = previous_timeout


@pytest.mark.asyncio
async def test_cache_store_after_fallback(monkeypatch, caplog):
    stored: dict[str, Any] = {}

    async def fake_get(self, route, prompt):
        return None

    async def fake_set(self, route, prompt, response, ttl):
        stored["payload"] = response
        stored["ttl"] = ttl

    monkeypatch.setattr(AICacheService, "get", fake_get)
    monkeypatch.setattr(AICacheService, "set", fake_set)

    service = AIService()
    service._ai_cache_service = AICacheService()

    async def fake_generate_response(message: str) -> str:
        return "fallback local"

    service.generate_response = fake_generate_response

    async def failing_backoff(*args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(service, "_call_with_backoff", failing_backoff)
    caplog.set_level(logging.INFO)

    result = await service.process_message("Forzar fallback")

    assert result.provider == "local"
    assert stored["payload"]["text"]
    assert any("cache_store" in record.message for record in caplog.records)
