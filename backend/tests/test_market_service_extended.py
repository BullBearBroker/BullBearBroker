from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

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


@dataclass
class _ExpiringStubCache:
    store: Dict[str, Any]
    default_ttl: int = 1
    now: float = 0.0
    sets: int = 0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    async def get(self, key: str) -> Optional[Any]:
        entry = self.store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry is not None and self.now >= expiry:
            self.store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = self.now + (ttl if ttl is not None else self.default_ttl)
        self.store[key] = (value, expiry)
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


@pytest.mark.asyncio
async def test_get_historical_ohlc_raises_when_yahoo_payload_incomplete(
    monkeypatch: pytest.MonkeyPatch, market_service: MarketService
) -> None:
    payload = {"chart": {"result": []}}

    dummy_response = _DummyResponse(status=200, payload=payload)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(dummy_response),
    )

    with pytest.raises(ValueError) as exc:
        await market_service.get_historical_ohlc("msft", interval="1h", market="stock")

    assert "Yahoo: Datos históricos no disponibles" in str(exc.value)


@pytest.mark.asyncio
async def test_history_cache_refetches_after_ttl_expiration(
    monkeypatch: pytest.MonkeyPatch, market_service: MarketService
) -> None:
    cache = _ExpiringStubCache({}, default_ttl=1)
    market_service.history_cache = cache  # type: ignore[assignment]

    calls: List[str] = []

    async def fake_fetch(self, symbol: str, interval: str, limit: int) -> Dict[str, Any]:
        calls.append(interval)
        return {
            "symbol": symbol,
            "interval": interval,
            "source": "Binance",
            "values": [
                {
                    "timestamp": "2024-01-01T00:00:00+00:00",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 1.0,
                }
            ],
        }

    monkeypatch.setattr(MarketService, "_fetch_binance_history", fake_fetch)

    await market_service.get_historical_ohlc("btcusdt", market="crypto")
    assert len(calls) == 1

    cache.advance(5)

    await market_service.get_historical_ohlc("btcusdt", market="crypto")
    assert len(calls) == 2
    assert cache.sets == 2


@pytest.mark.asyncio
async def test_get_historical_ohlc_raises_for_unsupported_interval(
    monkeypatch: pytest.MonkeyPatch, market_service: MarketService
) -> None:
    async def fake_binance(self, symbol: str, interval: str, limit: int) -> Dict[str, Any]:
        raise ValueError(f"Intervalo no soportado por Binance: {interval}")

    market_service.history_cache = _StubCache({})  # type: ignore[assignment]
    monkeypatch.setattr(MarketService, "_fetch_binance_history", fake_binance)

    with pytest.raises(ValueError) as exc:
        await market_service.get_historical_ohlc("btcusdt", interval="7m", market="crypto")

    assert "Intervalo no soportado" in str(exc.value)


@pytest.mark.asyncio
async def test_get_historical_ohlc_rejects_corrupted_yahoo_values(
    monkeypatch: pytest.MonkeyPatch, market_service: MarketService
) -> None:
    async def failing_binance(*_args: Any, **_kwargs: Any) -> None:
        raise ClientError("binance unavailable")

    corrupted_payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000],
                    "indicators": {
                        "quote": [
                            {
                                "open": ["bad"],
                                "high": ["101"],
                                "low": ["99"],
                                "close": ["100"],
                                "volume": ["50"],
                            }
                        ]
                    },
                }
            ]
        }
    }

    dummy_response = _DummyResponse(status=200, payload=corrupted_payload)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: _DummySession(dummy_response),
    )

    monkeypatch.setattr(MarketService, "_fetch_binance_history", failing_binance)

    with pytest.raises(ValueError) as exc:
        await market_service.get_historical_ohlc("aapl", interval="1h", market="stock")

    assert "Yahoo: could not convert string to float" in str(exc.value)


@pytest.mark.asyncio
async def test_fetch_binance_history_raises_when_all_entries_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        [1700000000000, None, "110", "90", "105", "250"],
        [1700003600000, "NaN", "", None, "120", "400"],
    ]

    class _AsyncResponse:
        def __init__(self) -> None:
            self.status = 200
            self.json = AsyncMock(return_value=payload)
            self.text = AsyncMock(return_value="")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    response = _AsyncResponse()

    class _AsyncSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *_args, **_kwargs):
            return response

    session = _AsyncSession()

    monkeypatch.setattr(
        market_service_module.aiohttp, "ClientSession", lambda *args, **kwargs: session
    )

    market_service = MarketService()

    with pytest.raises(ValueError, match="Binance no devolvió datos"):
        await market_service._fetch_binance_history("BTCUSDT", "1h", 10)


@pytest.mark.asyncio
async def test_get_historical_ohlc_falls_back_when_binance_fails_with_asyncmock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binance_mock = AsyncMock(side_effect=ValueError("sin datos"))
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
    yahoo_mock = AsyncMock(return_value=yahoo_payload)

    market_service = MarketService()
    market_service.history_cache = _StubCache({})  # type: ignore[assignment]

    monkeypatch.setattr(MarketService, "_fetch_binance_history", binance_mock)
    monkeypatch.setattr(MarketService, "_fetch_yahoo_history", yahoo_mock)
    monkeypatch.setattr(MarketService, "_looks_like_crypto", lambda *_args, **_kwargs: True)

    result = await market_service.get_historical_ohlc("aapl", interval="1h", market="auto")

    assert result == yahoo_payload
    assert binance_mock.await_count == 1
    yahoo_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_historical_ohlc_uses_cached_value_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached_payload = {
        "symbol": "ETHUSDT",
        "interval": "1h",
        "source": "cache",
        "values": [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 2000.0,
                "high": 2100.0,
                "low": 1900.0,
                "close": 2050.0,
                "volume": 123.0,
            }
        ],
    }

    cache = _StubCache({"ethusdt:1h:300:auto": cached_payload})
    market_service = MarketService()
    market_service.history_cache = cache  # type: ignore[assignment]

    binance_mock = AsyncMock()
    yahoo_mock = AsyncMock()
    monkeypatch.setattr(MarketService, "_fetch_binance_history", binance_mock)
    monkeypatch.setattr(MarketService, "_fetch_yahoo_history", yahoo_mock)

    result = await market_service.get_historical_ohlc("ETHUSDT", interval="1h", market="auto")

    assert result == cached_payload
    binance_mock.assert_not_called()
    yahoo_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_historical_ohlc_cache_expiration_triggers_new_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = _ExpiringStubCache({}, default_ttl=1)
    market_service = MarketService()
    market_service.history_cache = cache  # type: ignore[assignment]

    payload = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "source": "Binance",
        "values": [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
            }
        ],
    }

    binance_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(MarketService, "_fetch_binance_history", binance_mock)
    monkeypatch.setattr(MarketService, "_looks_like_crypto", lambda *_args, **_kwargs: True)

    await market_service.get_historical_ohlc("BTCUSDT", interval="1h", market="auto")
    cache.advance(10)
    await market_service.get_historical_ohlc("BTCUSDT", interval="1h", market="auto")

    assert binance_mock.await_count == 2


@pytest.mark.asyncio
async def test_get_historical_ohlc_returns_empty_dataset_when_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binance_mock = AsyncMock(side_effect=ValueError("sin datos"))
    fallback_payload = {
        "symbol": "AAPL",
        "interval": "1h",
        "source": "Fallback",
        "values": [],
    }
    yahoo_mock = AsyncMock(return_value=fallback_payload)

    market_service = MarketService()
    market_service.history_cache = _StubCache({})  # type: ignore[assignment]

    monkeypatch.setattr(MarketService, "_fetch_binance_history", binance_mock)
    monkeypatch.setattr(MarketService, "_fetch_yahoo_history", yahoo_mock)
    monkeypatch.setattr(MarketService, "_looks_like_crypto", lambda *_args, **_kwargs: False)

    result = await market_service.get_historical_ohlc("AAPL", interval="1h", market="stock")

    assert result == fallback_payload
    assert result["values"] == []
    yahoo_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_price_history_fetches_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000, 1700003600],
                    "indicators": {"quote": [{"close": [100.0, 101.5]}]},
                }
            ]
        }
    }
    dummy_response = _DummyResponse(status=200, payload=payload)
    session = _DummySession(dummy_response)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: session,
    )

    market_service = MarketService()
    market_service.chart_cache = _StubCache({})  # type: ignore[assignment]

    history = await market_service.get_price_history("AAPL", interval="1h", range_="1mo")
    assert len(history["values"]) == 2
    assert history["values"][0]["close"] == pytest.approx(100.0)

    # Second call should hit cache and skip network
    history_cached = await market_service.get_price_history("AAPL", interval="1h", range_="1mo")
    assert history_cached == history


@pytest.mark.asyncio
async def test_get_price_history_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_response = _DummyResponse(status=500, payload=None, text="error")
    session = _DummySession(dummy_response)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: session,
    )

    with pytest.raises(ClientError):
        market_service = MarketService()
        market_service.chart_cache = _StubCache({})  # type: ignore[assignment]
        await market_service.get_price_history("AAPL")


@pytest.mark.asyncio
async def test_get_price_history_raises_when_payload_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"chart": {"result": [{}]}}
    dummy_response = _DummyResponse(status=200, payload=payload)
    session = _DummySession(dummy_response)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: session,
    )

    market_service = MarketService()
    market_service.chart_cache = _StubCache({})  # type: ignore[assignment]

    with pytest.raises(ValueError):
        await market_service.get_price_history("AAPL")


@pytest.mark.asyncio
async def test_fetch_binance_history_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error_response = _DummyResponse(status=500, payload=None, text="down")
    session = _DummySession(error_response)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: session,
    )

    market_service = MarketService()

    with pytest.raises(ClientError):
        await market_service._fetch_binance_history("BTCUSDT", "1h", 10)


@pytest.mark.asyncio
async def test_fetch_yahoo_history_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000, 1700003600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0, 101.0],
                                "high": [105.0, 106.0],
                                "low": [95.0, 98.0],
                                "close": [102.0, 104.0],
                                "volume": [1000, 2000],
                            }
                        ]
                    },
                }
            ]
        }
    }
    response = _DummyResponse(status=200, payload=payload)
    session = _DummySession(response)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: session,
    )

    market_service = MarketService()
    candles = await market_service._fetch_yahoo_history("AAPL", "1h", 10)

    assert candles["source"] == "Yahoo Finance"
    assert len(candles["values"]) == 2
    assert candles["values"][0]["open"] == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_fetch_yahoo_history_skips_none_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000, 1700003600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [None, 101.0],
                                "high": [None, 106.0],
                                "low": [None, 98.0],
                                "close": [None, 104.0],
                                "volume": [None, 2000],
                            }
                        ]
                    },
                }
            ]
        }
    }
    response = _DummyResponse(status=200, payload=payload)
    session = _DummySession(response)
    monkeypatch.setattr(
        market_service_module.aiohttp,
        "ClientSession",
        lambda *args, **kwargs: session,
    )

    market_service = MarketService()
    candles = await market_service._fetch_yahoo_history("AAPL", "1h", 10)

    assert len(candles["values"]) == 1
    assert candles["values"][0]["open"] == pytest.approx(101.0)


@pytest.mark.asyncio
async def test_get_historical_ohlc_returns_binance_data(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "source": "Binance",
        "values": [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 1.0,
                "high": 1.5,
                "low": 0.8,
                "close": 1.2,
                "volume": 10.0,
            }
        ],
    }
    binance_mock = AsyncMock(return_value=payload)
    market_service = MarketService()
    market_service.history_cache = _StubCache({})  # type: ignore[assignment]

    monkeypatch.setattr(MarketService, "_fetch_binance_history", binance_mock)
    monkeypatch.setattr(MarketService, "_looks_like_crypto", lambda *_args, **_kwargs: True)

    result = await market_service.get_historical_ohlc("btcusdt", interval="1h", market="crypto")

    assert result == payload
    assert binance_mock.await_count == 1


@pytest.mark.asyncio
async def test_get_historical_ohlc_raises_when_no_providers_available(monkeypatch: pytest.MonkeyPatch) -> None:
    market_service = MarketService()
    market_service.history_cache = _StubCache({})  # type: ignore[assignment]

    binance_mock = AsyncMock(side_effect=ValueError("binance error"))
    yahoo_mock = AsyncMock(side_effect=ValueError("yahoo error"))

    monkeypatch.setattr(MarketService, "_fetch_binance_history", binance_mock)
    monkeypatch.setattr(MarketService, "_fetch_yahoo_history", yahoo_mock)
    monkeypatch.setattr(MarketService, "_looks_like_crypto", lambda *_args, **_kwargs: True)

    with pytest.raises(ValueError) as exc:
        await market_service.get_historical_ohlc("btcusdt", interval="1h", market="auto")

    assert "Binance" in str(exc.value)
    assert "Yahoo" in str(exc.value)


def test_format_symbol_for_yahoo_variations() -> None:
    assert MarketService._format_symbol_for_yahoo("eur/usd") == "EURUSD=X"
    assert MarketService._format_symbol_for_yahoo("btc-usdt") == "BTCUSDT=X"
    assert MarketService._format_symbol_for_yahoo("aapl") == "AAPL"


def test_format_helpers_produce_expected_strings() -> None:
    service = MarketService()
    assert service._format_currency(1234.567) == "$1,234.57"
    assert service._format_currency(None) == "N/A"
    assert service._format_percent(2.5) == "+2.50%"
    assert service._format_percent(None) == "N/A"
    assert service._format_volume(1000.25) == "1,000"
    assert service._format_volume("bad") == "N/A"


def test_combine_ranked_lists_interleaves_sources() -> None:
    service = MarketService()
    combined = service._combine_ranked_lists(
        [[{"id": 1}, {"id": 3}], [{"id": 2}, {"id": 4}]], limit=3
    )
    assert [item["id"] for item in combined] == [1, 2, 3]


def test_format_performer_uses_format_helpers() -> None:
    service = MarketService()
    performer = service._format_performer(
        {"symbol": "AAPL", "price": 150.0, "raw_change": -1.5, "type": "stock", "source": "Test"}
    )
    assert performer["price"] == "$150.00"
    assert performer["change"] == "-1.50%"


def test_build_market_summary_includes_best_crypto() -> None:
    service = MarketService()
    stock_data = [
        {"raw_change": 2.0},
        {"raw_change": -1.0},
    ]
    crypto_data = {
        "top_gainers": [{"symbol": "BTC", "raw_change": 5.0}],
        "top_losers": [],
    }

    summary = service._build_market_summary(stock_data, crypto_data)
    assert summary["stocks_covered"] == 2
    assert summary["crypto_pairs"] == 1
    assert summary["avg_stock_change"] == "+0.50%"
    assert summary["best_crypto"]["symbol"] == "BTC"
    assert "generated_at" in summary


def test_normalize_datetime_handles_various_inputs() -> None:
    service = MarketService()
    iso_value = service._normalize_datetime("2024-01-01T00:00:00Z")
    assert iso_value == "2024-01-01T00:00:00+00:00"

    rfc_value = service._normalize_datetime("Mon, 01 Jan 2024 00:00:00 GMT")
    assert rfc_value.startswith("2024-01-01T00:00:00")

    assert service._normalize_datetime("bad-value") is None


def test_clean_html_and_extract_domain() -> None:
    service = MarketService()
    assert service._clean_html("<p>Hello &amp; goodbye</p>") == "Hello & goodbye"
    assert service._extract_domain("https://example.com/page") == "example.com"
    assert service._extract_domain(None) == "Unknown"


@pytest.mark.asyncio
async def test_detect_asset_type_identifies_crypto() -> None:
    service = MarketService()
    assert await service.detect_asset_type("btc") == "crypto"
    assert await service.detect_asset_type("aapl") == "stock"


@pytest.mark.asyncio
async def test_get_price_formats_crypto_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    monkeypatch.setattr(MarketService, "detect_asset_type", AsyncMock(return_value="crypto"))
    crypto_payload = {
        "price": 100.0,
        "raw_change": 5.0,
        "high": 110.0,
        "low": 90.0,
        "volume": 1234.0,
        "source": "TestSource",
    }
    monkeypatch.setattr(MarketService, "get_crypto_price", AsyncMock(return_value=crypto_payload))

    formatted = await service.get_price("btc")
    assert formatted["price"] == "$100.00"
    assert formatted["change"] == "+5.00%"
    assert formatted["volume"] == "1,234"


@pytest.mark.asyncio
async def test_get_price_formats_stock_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    monkeypatch.setattr(MarketService, "detect_asset_type", AsyncMock(return_value="stock"))
    stock_payload = {
        "price": 50.0,
        "raw_change": -1.25,
        "high": None,
        "low": None,
        "volume": None,
        "source": "StockSource",
    }
    monkeypatch.setattr(MarketService, "get_stock_price", AsyncMock(return_value=stock_payload))

    formatted = await service.get_price("aapl")
    assert formatted["change"] == "-1.25%"
    assert formatted["high"] == "N/A"


@pytest.mark.asyncio
async def test_get_crypto_price_merges_binance_data(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()

    crypto_service_mock = AsyncMock(return_value=120.0)
    service.crypto_service.get_price = crypto_service_mock  # type: ignore[assignment]

    binance_payload = {
        "price": 125.0,
        "change": 2.0,
        "high": 130.0,
        "low": 110.0,
        "volume": 2000.0,
        "source": "Binance",
    }
    monkeypatch.setattr(MarketService, "get_binance_price", AsyncMock(return_value=binance_payload))

    result = await service.get_crypto_price("btc")
    assert result["source"] == "CryptoService + Binance"
    assert result["price"] == pytest.approx(120.0)
    assert result["volume"] == pytest.approx(2000.0)


@pytest.mark.asyncio
async def test_get_crypto_price_returns_none_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    service.crypto_service.get_price = AsyncMock(return_value=None)  # type: ignore[assignment]
    monkeypatch.setattr(MarketService, "get_binance_price", AsyncMock(return_value=None))

    assert await service.get_crypto_price("unknown") is None


@pytest.mark.asyncio
async def test_get_stock_price_handles_non_numeric_change(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    service.stock_service.get_price = AsyncMock(return_value={"price": 200.0, "change": "bad", "source": "Test"})  # type: ignore[assignment]

    result = await service.get_stock_price("aapl")
    assert result["raw_change"] is None
    assert result["price"] == pytest.approx(200.0)


@pytest.mark.asyncio
async def test_get_stock_market_data_filters_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    stock_mock = AsyncMock(side_effect=[
        {"symbol": "AAPL", "raw_change": 1.0},
        Exception("boom"),
        None,
    ])
    monkeypatch.setattr(MarketService, "get_stock_price", stock_mock)

    results = await service.get_stock_market_data(["AAPL", "MSFT", "TSLA"])
    assert results == [{"symbol": "AAPL", "raw_change": 1.0}]


@pytest.mark.asyncio
async def test_get_crypto_market_data_filters_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    crypto_mock = AsyncMock(side_effect=[
        {"symbol": "BTC", "raw_change": 2.0},
        None,
    ])
    monkeypatch.setattr(MarketService, "get_crypto_price", crypto_mock)

    results = await service.get_crypto_market_data(["BTC", "ETH"])
    assert results == [{"symbol": "BTC", "raw_change": 2.0}]


@pytest.mark.asyncio
async def test_process_market_data_combines_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    stock_data = [
        {"symbol": "AAPL", "price": 100.0, "raw_change": 3.0, "type": "stock"},
        {"symbol": "MSFT", "price": 90.0, "raw_change": -2.0, "type": "stock"},
    ]
    crypto_data = {
        "top_gainers": [{"symbol": "BTC", "price": 200.0, "raw_change": 5.0, "type": "crypto"}],
        "top_losers": [{"symbol": "ETH", "price": 150.0, "raw_change": -4.0, "type": "crypto"}],
    }

    summary = await service.process_market_data(stock_data, crypto_data)
    assert summary["top_performers"]
    assert summary["worst_performers"]
    assert summary["market_summary"]["stocks_covered"] == 2


@pytest.mark.asyncio
async def test_get_top_performers_uses_real_data(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    service.news_cache = _StubCache({})  # ensure simple caches

    binance_payload = {
        "top_gainers": [{"symbol": "BTC", "price": 200.0, "raw_change": 5.0, "type": "crypto"}],
        "top_losers": [{"symbol": "ETH", "price": 150.0, "raw_change": -4.0, "type": "crypto"}],
    }
    stock_payload = [
        {"symbol": "AAPL", "price": 100.0, "raw_change": 2.0, "type": "stock"}
    ]

    monkeypatch.setattr(MarketService, "get_binance_top_performers", AsyncMock(return_value=binance_payload))
    monkeypatch.setattr(MarketService, "get_stock_market_data", AsyncMock(return_value=stock_payload))

    result = await service.get_top_performers()
    assert "top_performers" in result
    assert result["top_performers"]


@pytest.mark.asyncio
async def test_get_top_performers_falls_back_to_simulated(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    simulated = {"top_performers": [], "worst_performers": [], "market_summary": {}}
    monkeypatch.setattr(MarketService, "get_binance_top_performers", AsyncMock(side_effect=Exception("fail")))
    monkeypatch.setattr(MarketService, "get_stock_market_data", AsyncMock(return_value=[]))
    monkeypatch.setattr(MarketService, "process_market_data", AsyncMock(side_effect=ValueError("no data")))
    monkeypatch.setattr(MarketService, "get_simulated_data", AsyncMock(return_value=simulated))

    result = await service.get_top_performers()
    assert result == simulated


@pytest.mark.asyncio
async def test_get_simulated_data_structure() -> None:
    service = MarketService()
    data = await service.get_simulated_data()
    assert data["top_performers"] == []
    assert "note" in data["market_summary"]


@pytest.mark.asyncio
async def test_get_news_uses_cache_and_rss(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketService()
    cache = _StubCache({})
    service.news_cache = cache  # type: ignore[assignment]

    monkeypatch.setattr(market_service_module.Config, "NEWSAPI_API_KEY", "")
    monkeypatch.setattr(market_service_module.Config, "MEDIASTACK_API_KEY", "", raising=False)

    rss_payload = [
        {
            "title": "Sample",
            "url": "https://example.com/article",
            "source": "Example",
            "published_at": "2024-01-01T00:00:00Z",
            "summary": "Content",
        }
    ]
    monkeypatch.setattr(MarketService, "_fetch_rss", AsyncMock(return_value=rss_payload))

    articles = await service.get_news("AAPL", limit=1)
    assert len(articles) == 1

    # second call should come from cache
    cached = await service.get_news("AAPL", limit=1)
    assert cached == articles
