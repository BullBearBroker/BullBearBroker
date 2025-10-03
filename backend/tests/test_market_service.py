from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from backend.services import market_service as market_service_module
from backend.services.market_service import MarketService


@dataclass
class _DummyCryptoService:
    async def get_price(self, symbol: str) -> float | None:  # pragma: no cover - helper
        return None


@dataclass
class _DummyStockService:
    async def get_price(
        self, symbol: str
    ) -> dict[str, Any] | None:  # pragma: no cover - helper
        return None


class _DummyCache:
    def __init__(self, *_args, **_kwargs) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._store[key] = value


@pytest.fixture()
def service(monkeypatch: pytest.MonkeyPatch) -> MarketService:
    monkeypatch.setattr(market_service_module, "CacheClient", _DummyCache)
    monkeypatch.setattr(
        market_service_module, "CryptoService", lambda: _DummyCryptoService()
    )
    monkeypatch.setattr(
        market_service_module, "StockService", lambda: _DummyStockService()
    )
    return MarketService()


@pytest.mark.asyncio
async def test_get_historical_ohlc_from_binance(
    service: MarketService, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "source": "Binance",
        "values": [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 42000.0,
                "high": 42100.0,
                "low": 41950.0,
                "close": 42050.0,
                "volume": 10.0,
            },
            {
                "timestamp": "2024-01-01T01:00:00+00:00",
                "open": 42050.0,
                "high": 42200.0,
                "low": 42010.0,
                "close": 42180.0,
                "volume": 12.0,
            },
        ],
    }

    async def fake_fetch(
        self, symbol: str, interval: str, limit: int
    ) -> dict[str, Any]:
        assert symbol == "BTCUSDT"
        assert interval == "1h"
        assert limit >= 10  # método garantiza mínimo
        return payload

    monkeypatch.setattr(MarketService, "_fetch_binance_history", fake_fetch)

    result = await service.get_historical_ohlc(
        "btcusdt", interval="1h", limit=50, market="crypto"
    )

    assert result["symbol"] == "BTCUSDT"
    assert result["source"] == "Binance"
    assert isinstance(result["values"], list)
    assert len(result["values"]) == len(payload["values"])
    assert result["values"][0]["close"] == pytest.approx(42050.0)


@pytest.mark.asyncio
async def test_get_historical_ohlc_raises_when_provider_fails(
    service: MarketService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_fetch(
        self, symbol: str, interval: str, limit: int
    ) -> dict[str, Any]:
        raise RuntimeError("Binance unavailable")

    monkeypatch.setattr(MarketService, "_fetch_binance_history", failing_fetch)

    with pytest.raises(RuntimeError):
        await service.get_historical_ohlc("ethusdt", market="crypto")


@pytest.mark.asyncio
async def test_get_historical_ohlc_returns_empty_values(
    service: MarketService, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "source": "Binance",
        "values": [],
    }

    async def empty_fetch(
        self, symbol: str, interval: str, limit: int
    ) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(MarketService, "_fetch_binance_history", empty_fetch)

    result = await service.get_historical_ohlc("btcusdt", market="crypto")

    assert result["values"] == []
    assert result["symbol"] == "BTCUSDT"
