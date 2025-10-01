from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.services import ai_service as ai_service_module
from backend.services.ai_service import AIService


class _DummySession:
    """Minimal async context manager emulating :class:`aiohttp.ClientSession`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 - signature mirrors aiohttp
        self.args = args
        self.kwargs = kwargs
        self.closed = False

    async def __aenter__(self) -> "_DummySession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - standard context manager
        self.closed = True


@pytest.mark.asyncio
async def test_collect_indicator_snapshots_filters_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIService()

    # Aseguramos URL base consistente para validar parámetros enviados
    monkeypatch.setattr(ai_service_module.Config, "API_BASE_URL", "http://example.com", raising=False)

    async def fake_resolve(self: AIService, symbol: str) -> str | None:
        mapping = {"btc": "crypto", "eurusd": "forex"}
        return mapping.get(symbol.lower())

    captured_params: List[Dict[str, str]] = []

    async def fake_fetch(self: AIService, session: Any, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        captured_params.append(params.copy())
        if params["symbol"] == "BTCUSDT":
            return {
                "interval": params["interval"],
                "source": "stub",
                "indicators": {"rsi": {"value": 55.0}},
            }
        raise RuntimeError("downstream failure")

    monkeypatch.setattr(AIService, "_resolve_asset_type", fake_resolve)
    monkeypatch.setattr(AIService, "_fetch_indicator_snapshot", fake_fetch)
    monkeypatch.setattr(ai_service_module.aiohttp, "ClientSession", _DummySession)

    result = await service._collect_indicator_snapshots("Analiza BTC y EURUSD en 1h")

    assert result == {
        "BTC": {
            "asset_type": "crypto",
            "interval": "1h",
            "source": "stub",
            "indicators": {"rsi": {"value": 55.0}},
        }
    }

    assert captured_params[0]["symbol"] == "BTCUSDT"


def test_merge_indicator_response_appends_summary() -> None:
    service = AIService()

    indicator_map = {
        "BTC": {
            "interval": "1h",
            "indicators": {
                "rsi": {"value": 48.5},
                "macd": {"macd": -0.12},
                "atr": {"value": 1.23},
                "stochastic_rsi": {"%K": 70.0},
                "ichimoku": {"tenkan_sen": 25.0, "kijun_sen": 30.0},
                "vwap": {"value": 27_000.5},
            },
        },
        "ETH": {"interval": "1h", "indicators": {}},  # sin datos válidos -> se ignora
    }

    merged = service._merge_indicator_response("Base", indicator_map)

    assert merged.startswith("Base")
    assert "📊 Indicadores recientes" in merged
    assert "BTC (1h):" in merged
    assert "RSI 48.5" in merged
    assert "MACD -0.12" in merged
    assert "ATR 1.23" in merged
    assert "StochRSI %K 70.0" in merged
    assert "Ichimoku T/K 25.0/30.0" in merged
    assert "VWAP 27000.5" in merged
    # ETH no aporta indicadores -> no aparece en el resumen
    assert "ETH" not in merged


def test_normalize_symbol_for_indicators_handles_multiple_asset_types() -> None:
    service = AIService()

    assert service._normalize_symbol_for_indicators("crypto", "btc") == "BTCUSDT"
    assert service._normalize_symbol_for_indicators("forex", "eur/usd") == "EURUSD"
    assert service._normalize_symbol_for_indicators("stock", "aapl") == "AAPL"


@pytest.mark.asyncio
async def test_looks_like_forex_pair_and_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIService()

    assert service._looks_like_forex_pair("EUR/USD") is True
    assert service._looks_like_forex_pair("EURUSD") is True
    assert service._looks_like_forex_pair("BTC") is False

    async def fake_detect(symbol: str) -> str | None:
        raise RuntimeError("market unavailable")

    mock_market = type("_MarketStub", (), {"detect_asset_type": fake_detect})()
    service.set_market_service(mock_market)

    # Cuando el MarketService falla, se aplica heurística por defecto a 'stock'
    resolved = await service._resolve_asset_type("tsla")
    assert resolved == "stock"

