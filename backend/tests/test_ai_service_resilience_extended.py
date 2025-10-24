"""Pruebas extendidas de resiliencia para el servicio de IA."""

from __future__ import annotations

import asyncio
import json
import logging
import time

import pytest

from backend.metrics.ai_metrics import (
    ai_failures_total,
    ai_fallbacks_total,
    ai_latency_seconds,
    ai_requests_total,
)
from backend.services.ai_service import PROVIDER_TIMEOUTS, AIService


@pytest.fixture(autouse=True)
def ensure_mistral_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mistral")


@pytest.fixture(autouse=True)
def reset_ai_metrics() -> None:
    """Reinicia los contadores Prometheus entre pruebas."""

    # ✅ Codex fix: asegurar aislamiento métrico
    ai_requests_total._metrics.clear()  # type: ignore[attr-defined]
    ai_failures_total._metrics.clear()  # type: ignore[attr-defined]
    ai_fallbacks_total._metrics.clear()  # type: ignore[attr-defined]
    ai_latency_seconds._metrics.clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_mistral_circuit_breaker_triggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los fallos consecutivos de Mistral activan el circuit breaker y hacen fallback."""

    service = AIService()

    async def fast_sleep(_: float) -> None:  # noqa: D401 - helper interno
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    calls = {"mistral": 0, "hugging": 0}

    async def mistral_failure() -> str:
        calls["mistral"] += 1
        raise RuntimeError("mistral down")

    async def huggingface_success() -> str:
        calls["hugging"] += 1
        return "ok"

    result, provider = await service._call_with_backoff(
        [
            ("mistral", mistral_failure),
            ("huggingface", huggingface_success),
        ]
    )

    assert result == "ok"
    assert provider == "huggingface"
    assert calls["mistral"] == service._max_retries

    circuit = service._get_circuit("mistral")
    assert circuit.state == "open"

    calls_before_second = calls["mistral"]
    result_repeat, provider_repeat = await service._call_with_backoff(
        [
            ("mistral", mistral_failure),
            ("huggingface", huggingface_success),
        ]
    )

    assert result_repeat == "ok"
    assert provider_repeat == "huggingface"
    assert calls["mistral"] == calls_before_second  # saltado por circuit breaker


@pytest.mark.asyncio
async def test_provider_timeout_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    """El timeout adaptativo limita la espera por proveedor."""

    service = AIService()
    service._max_retries = 1  # ejecutar una sola vez para medir tiempo
    monkeypatch.setitem(PROVIDER_TIMEOUTS, "mistral", 0.2)

    async def slow_provider() -> str:
        await asyncio.sleep(1)
        return "never"

    start = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await service._call_with_backoff([("mistral", slow_provider)])
    elapsed = time.perf_counter() - start

    assert elapsed <= PROVIDER_TIMEOUTS["mistral"] + 0.2


@pytest.mark.asyncio
async def test_structured_logs_emitted(caplog: pytest.LogCaptureFixture) -> None:
    """Las llamadas generan logs JSON con ai_event."""

    service = AIService()
    caplog.set_level(logging.INFO)

    async def ok_provider() -> str:
        return "done"

    await service._call_with_backoff([("mistral", ok_provider)])

    structured = [
        json.loads(record.message)
        for record in caplog.records
        if record.levelno == logging.INFO
        and record.message.startswith("{")
        and "ai_event" in record.message
    ]

    assert structured, "Debe existir al menos un log estructurado ai_event"
    assert any(entry.get("ai_event") == "provider_call" for entry in structured)


@pytest.mark.asyncio
async def test_ai_metrics_increment_on_calls() -> None:
    """Las métricas de requests y fallos se actualizan tras las llamadas."""

    service = AIService()

    async def failing_provider() -> str:
        raise ValueError("provider down")

    async def successful_provider() -> str:
        return "all good"

    result, provider = await service._call_with_backoff(
        [
            ("mistral", failing_provider),
            ("huggingface", successful_provider),
        ]
    )

    assert result == "all good"
    assert provider == "huggingface"

    failure_metric = ai_failures_total.labels(
        provider="mistral", error_type="ValueError"
    )._value.get()  # type: ignore[attr-defined]
    assert failure_metric >= 1

    success_metric = ai_requests_total.labels(outcome="success")._value.get()  # type: ignore[attr-defined]
    assert success_metric == 1

    failure_requests = ai_requests_total.labels(outcome="error")._value.get()  # type: ignore[attr-defined]
    assert failure_requests >= 1
