from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest
from aiohttp import ClientError

from backend.services import market_service as market_service_module
from backend.services.market_service import MarketService


class _DummyResponse:
    def __init__(self, status: int, payload: Any, text: str = "") -> None:
        self.status = status
        self._payload = payload
        self._text = text or ""

    async def __aenter__(self):  # noqa: D401 - simple async context helper
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def text(self) -> str:
        return self._text


class _DummySession:
    def __init__(self, response: _DummyResponse) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def get(self, *_args, **_kwargs) -> _DummyResponse:
        return self._response


@dataclass
class _StubCache:
    store: Dict[str, Any]
    sets: int = 0

    async def get(self, key: str) -> Optional[Any]:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.store[key] = value
        self.sets += 1


@pytest.fixture()
def market_service(monkeypatch: pytest.MonkeyPatch) -> MarketService:
    monkeypatch.setattr(market_service_module, "CacheClient", lambda *args, **kwargs: _StubCache({}))
    return MarketService()


@pytest.mark.asyncio
async def test_fetch_binance_history_normalizes_payload(monkeypatch: pytest.MonkeyPatch, market_service: MarketService) -> None:
    payload = [
        [1700000000000, "100", "110", "90", "105", "250"],
        [1700003600000, "105", "120", "100", "118", "400"],
    ]

    dummy_response = _DummyResponse(status=200, payload=payload)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(dummy_response),
    )

    result = await market_service._fetch_binance_history("BTCUSDT", "1h", 100)
    assert result["source"] == "Binance"
    assert len(result["values"]) == 2
    first = result["values"][0]
    assert first["open"] == pytest.approx(100.0)
    assert first["volume"] == pytest.approx(250.0)


@pytest.mark.asyncio
async def test_get_historical_ohlc_falls_back_to_yahoo(monkeypatch: pytest.MonkeyPatch, market_service: MarketService) -> None:
    async def failing_binance(*_args, **_kwargs):
        raise ClientError("binance down")

    yahoo_payload = {
        "symbol": "AAPL",
        "interval": "1h",
        "source": "Yahoo Finance",
        "values": [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        ],
    }

    cache = _StubCache({})
    market_service.history_cache = cache  # type: ignore[assignment]

    async def fake_yahoo(*_args, **_kwargs):
        return yahoo_payload

    monkeypatch.setattr(MarketService, "_fetch_binance_history", failing_binance)
    monkeypatch.setattr(MarketService, "_fetch_yahoo_history", fake_yahoo)

    result = await market_service.get_historical_ohlc("aapl", market="auto")

    assert result == yahoo_payload
    assert cache.sets == 1


@pytest.mark.asyncio
async def test_get_historical_ohlc_raises_when_yahoo_returns_error(monkeypatch: pytest.MonkeyPatch, market_service: MarketService) -> None:
    async def failing_binance(*_args, **_kwargs):
        raise ClientError("binance down")

    error_response = _DummyResponse(status=429, payload=None, text="rate limited")
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(error_response),
    )

    monkeypatch.setattr(MarketService, "_fetch_binance_history", failing_binance)

    with pytest.raises(ValueError) as exc:
        await market_service.get_historical_ohlc("msft", market="stock")

    assert "429" in str(exc.value)


@pytest.mark.asyncio
async def test_fetch_binance_history_raises_for_corrupted_payload(monkeypatch: pytest.MonkeyPatch, market_service: MarketService) -> None:
    payload = [["bad-entry"]]
    dummy_response = _DummyResponse(status=200, payload=payload)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(dummy_response),
    )

    with pytest.raises(ValueError):
        await market_service._fetch_binance_history("BTCUSDT", "1h", 10)


@pytest.mark.asyncio
async def test_history_cache_hit_skips_fetch(monkeypatch: pytest.MonkeyPatch, market_service: MarketService) -> None:
    calls: List[str] = []

    async def fake_fetch(self, symbol: str, interval: str, limit: int) -> Dict[str, Any]:
        calls.append(symbol)
        return {
            "symbol": symbol,
            "interval": interval,
            "source": "Binance",
            "values": [],
        }

    cache = _StubCache({})
    market_service.history_cache = cache  # type: ignore[assignment]
    monkeypatch.setattr(MarketService, "_fetch_binance_history", fake_fetch)

    await market_service.get_historical_ohlc("ethusdt", market="crypto")
    assert calls == ["ETHUSDT"]
    assert cache.sets == 1

    cached = await market_service.get_historical_ohlc("ethusdt", market="crypto")
    assert cached["symbol"] == "ETHUSDT"
    assert calls == ["ETHUSDT"]  # no new fetch


@pytest.mark.asyncio
async def test_fetch_binance_history_rejects_invalid_interval(market_service: MarketService) -> None:
    with pytest.raises(ValueError):
        await market_service._fetch_binance_history("BTCUSDT", "7m", 10)
