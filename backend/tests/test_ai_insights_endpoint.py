import importlib

import pytest

from backend.metrics.ai_metrics import (
    ai_insight_failures_total,
    ai_insights_generated_total,
)
from backend.services.ai_service import AIResponsePayload, AIService
from backend.services.market_service import MarketService


@pytest.mark.asyncio
async def test_ai_insights_endpoint_success(async_client, monkeypatch):
    async def fake_get_historical(
        self, symbol, *, timeframe="1d", limit=120, market="auto"
    ):
        return [
            {"timestamp": "2024-01-01T00:00:00Z", "close": 100.0},
            {"timestamp": "2024-01-02T00:00:00Z", "close": 101.0},
        ]

    monkeypatch.setattr(MarketService, "get_historical", fake_get_historical)

    def fake_analyze_sentiment(_: str):
        return {"label": "positive", "score": 0.85}

    sentiment_module = importlib.import_module("backend.services.sentiment_service")
    monkeypatch.setattr(sentiment_module, "analyze_sentiment", fake_analyze_sentiment)

    async def fake_process_message(self, prompt: str):
        return AIResponsePayload(text="Recomendamos compra", provider="mock")

    monkeypatch.setattr(AIService, "process_message", fake_process_message)

    baseline = ai_insights_generated_total._value.get()

    response = await async_client.post(
        "/api/ai/insights",
        json={"symbol": "AAPL", "timeframe": "1d", "profile": "investor"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "AAPL"
    assert payload["profile"] == "investor"
    assert "insight" in payload and payload["insight"]

    updated = ai_insights_generated_total._value.get()
    assert updated >= baseline + 1


@pytest.mark.asyncio
async def test_ai_insights_endpoint_handles_failure(async_client, monkeypatch):
    async def failing_get_historical(
        self, symbol, *, timeframe="1d", limit=120, market="auto"
    ):
        raise RuntimeError("provider failure")

    monkeypatch.setattr(MarketService, "get_historical", failing_get_historical)

    failures_before = ai_insight_failures_total._value.get()

    response = await async_client.post("/api/ai/insights", json={"symbol": "TSLA"})

    assert response.status_code == 500
    detail = response.json().get("detail")
    assert "provider failure" in detail

    failures_after = ai_insight_failures_total._value.get()
    assert failures_after >= failures_before + 1
