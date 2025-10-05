import asyncio
import json
import logging
import time
from typing import Any

import pytest
from prometheus_client import REGISTRY

from backend.metrics.ai_metrics import (
    ai_provider_failures_total,
    ai_provider_fallbacks_total,
    ai_provider_latency_seconds,
    ai_provider_requests_total,
)
from backend.services import ai_service as ai_service_module
from backend.services import mistral_service as mistral_module
from backend.services.ai_service import ai_service
from backend.services.cache_service import cache
from backend.utils.config import Config


class FakeResponse:
    def __init__(
        self,
        status: int,
        *,
        text: str = "",
        json_data: Any = None,
        delay: float = 0.0,
    ) -> None:
        self.status = status
        self._text = text
        self._json_data = json_data
        self._delay = delay

    async def json(self) -> Any:
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._json_data

    async def text(self) -> str:
        return self._text


class FakePostContext:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> FakeResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: D401
        return False


class FakeClientSession:
    def __init__(self, *args, **kwargs) -> None:
        self._closed = False

    async def __aenter__(self) -> "FakeClientSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: D401
        return False

    def post(self, url: str, **kwargs) -> FakePostContext:
        if "mistral" in url:
            response = FakeResponse(429, text="Too Many Requests")
        else:
            response = FakeResponse(
                200,
                text="",
                json_data=[{"generated_text": "Respuesta HuggingFace"}],
                delay=0.02,
            )
        return FakePostContext(response)


def _reset_metrics() -> None:
    ai_provider_requests_total.clear()
    ai_provider_failures_total.clear()
    ai_provider_latency_seconds.clear()
    ai_provider_fallbacks_total.clear()


def _get_hist_sum(provider: str, route: str) -> float:
    sample = REGISTRY.get_sample_value(
        "ai_provider_latency_seconds_sum",
        {"provider": provider, "route": route},
    )
    return sample or 0.0


@pytest.mark.asyncio
async def test_ai_provider_metrics_and_logs(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    _reset_metrics()
    ai_service._cooldowns.clear()
    if isinstance(getattr(cache, "client", None), dict):
        cache.client.clear()

    monkeypatch.setattr(Config, "HUGGINGFACE_API_KEY", "test-token")
    monkeypatch.setattr(Config, "HUGGINGFACE_API_URL", "https://fake.hf")
    monkeypatch.setattr(Config, "HUGGINGFACE_MODEL", "fake-model")

    mistral_module.mistral_service.api_key = "test"
    mistral_module.mistral_service.max_retries = 1
    monkeypatch.setattr(ai_service, "_max_retries", 1)
    monkeypatch.setattr(
        mistral_module.MistralService,
        "_build_model_fallback",
        lambda self, preferred: ["medium"],
    )

    monkeypatch.setattr(
        mistral_module.aiohttp, "ClientSession", FakeClientSession
    )
    monkeypatch.setattr(
        ai_service_module.aiohttp, "ClientSession", FakeClientSession
    )

    async def _empty_dict(*args, **kwargs):
        return {}

    async def _empty_list(*args, **kwargs):
        return []

    monkeypatch.setattr(
        ai_service,
        "get_market_context",
        _empty_dict.__get__(ai_service, ai_service.__class__),
    )
    monkeypatch.setattr(
        ai_service,
        "_collect_indicator_snapshots",
        _empty_dict.__get__(ai_service, ai_service.__class__),
    )
    monkeypatch.setattr(
        ai_service,
        "_collect_news_highlights",
        _empty_list.__get__(ai_service, ai_service.__class__),
    )
    monkeypatch.setattr(
        ai_service,
        "_collect_alert_suggestions",
        _empty_list.__get__(ai_service, ai_service.__class__),
    )
    monkeypatch.setattr(
        ai_service,
        "_collect_forex_quotes",
        _empty_list.__get__(ai_service, ai_service.__class__),
    )

    first_response = await ai_service.process_message("Analiza BTC")
    assert first_response.provider == "huggingface"
    assert "HuggingFace" in first_response.text

    assert (
        ai_provider_requests_total.labels("Mistral", "sync")._value.get() == 1.0
    )
    assert (
        ai_provider_failures_total.labels("Mistral", "rate_limited", "sync")
        ._value.get()
        == 1.0
    )
    assert (
        ai_provider_requests_total.labels("HuggingFace", "sync")._value.get()
        == 1.0
    )
    assert _get_hist_sum("HuggingFace", "sync") >= 0.02
    assert (
        ai_provider_fallbacks_total.labels("Mistral", "HuggingFace", "sync")
        ._value.get()
        == 1.0
    )

    cooldown_deadline = ai_service._cooldowns.get(("Mistral", "sync"))
    assert cooldown_deadline is not None

    ai_service._cooldowns[("Mistral", "sync")] = time.monotonic() + 5

    providers = [
        ("mistral", lambda: ai_service.process_with_mistral("Analiza BTC", {})),
        (
            "huggingface",
            lambda: ai_service._call_huggingface("Analiza BTC", {}),
        ),
    ]

    result_text, result_provider = await ai_service._call_with_backoff(providers)
    assert result_provider == "huggingface"
    assert "HuggingFace" in result_text

    assert (
        ai_provider_requests_total.labels("Mistral", "sync")._value.get() == 1.0
    )
    assert (
        ai_provider_requests_total.labels("HuggingFace", "sync")._value.get()
        == 2.0
    )
    assert (
        ai_provider_fallbacks_total.labels("Mistral", "cooldown_skip", "sync")
        ._value.get()
        == 1.0
    )
    log_payloads: list[dict[str, Any]] = []
    for record in caplog.records:
        try:
            log_payloads.append(json.loads(record.message))
        except (TypeError, json.JSONDecodeError):
            continue

    provider_calls = [
        entry
        for entry in log_payloads
        if entry.get("ai_event") == "provider_call"
    ]
    assert any(
        entry.get("provider") == "Mistral"
        and entry.get("status") == "error"
        for entry in provider_calls
    )
    assert any(
        entry.get("provider") == "HuggingFace"
        and entry.get("status") == "ok"
        for entry in provider_calls
    )
    assert any(
        entry.get("ai_event") == "provider_fallback"
        and entry.get("from") == "Mistral"
        and entry.get("to") == "HuggingFace"
        and entry.get("route") == "sync"
        for entry in log_payloads
    )
    assert any(
        entry.get("ai_event") == "cooldown_skip" and entry.get("route") == "sync"
        for entry in log_payloads
    )
    ai_service._cooldowns.clear()
    if isinstance(getattr(cache, "client", None), dict):
        cache.client.clear()
