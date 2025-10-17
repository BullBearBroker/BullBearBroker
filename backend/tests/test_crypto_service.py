import asyncio
import os
import sys
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException  # noqa: E402

from backend.routers.markets import get_crypto  # noqa: E402

# 🔧 Ajuste: imports corregidos
from backend.services.crypto_service import CryptoService  # noqa: E402
from backend.services.market_service import market_service  # noqa: E402
from backend.utils.config import Config  # noqa: E402

crypto_service = market_service.crypto_service


class DummyCache:
    def __init__(self):
        self.values: dict[str, Any] = {}

    async def get(self, key: str):
        return self.values.get(key.lower())

    async def set(self, key: str, value: Any, ttl: Any = None):  # noqa: ARG002
        self.values[key.lower()] = value


def test_coingecko_symbol_resolution(monkeypatch):
    service = CryptoService(cache_client=DummyCache())

    expected_calls: list[dict[str, Any]] = []

    async def fake_request(self, url: str, *, session=None, **kwargs):
        if not expected_calls:
            pytest.fail("Se realizaron más llamadas de las esperadas a _request_json")
        call = expected_calls.pop(0)
        assert url == call["url"]
        if "params" in call:
            assert kwargs.get("params") == call["params"]
        return call["response"]

    monkeypatch.setattr(CryptoService, "_request_json", fake_request)

    expected_calls.append(
        {
            "url": "https://api.coingecko.com/api/v3/simple/price",
            "params": {"ids": "bitcoin", "vs_currencies": "usd"},
            "response": {"bitcoin": {"usd": 30123.45}},
        }
    )

    price = asyncio.run(service.coingecko("bitcoin"))
    assert price == pytest.approx(30123.45)
    assert not expected_calls

    missing_price = asyncio.run(service.coingecko(""))
    assert missing_price is None
    assert not expected_calls


def test_binance_failure(monkeypatch):
    service = CryptoService(cache_client=DummyCache())

    async def fake_request(*args, **kwargs):
        raise aiohttp.ClientError("network down")

    monkeypatch.setattr(service, "_request_json", fake_request)

    result = asyncio.run(service.binance("BTC"))
    assert result is None


def test_coinmarketcap_invalid_response(monkeypatch):
    service = CryptoService(cache_client=DummyCache())
    monkeypatch.setattr(Config, "COINMARKETCAP_API_KEY", "fake-key", raising=False)

    async def fake_request(*args, **kwargs):
        return {"data": {"ETH": {"quote": {"USD": {}}}}}

    monkeypatch.setattr(service, "_request_json", fake_request)

    result = asyncio.run(service.coinmarketcap("BTC"))
    assert result is None


def test_twelvedata_success(monkeypatch):
    service = CryptoService(cache_client=DummyCache())
    monkeypatch.setattr(Config, "TWELVEDATA_API_KEY", "fake-key", raising=False)

    async def fake_request(self, url, *, session=None, params=None, **kwargs):
        assert "twelvedata" in url
        assert params == {"symbol": "BTC/USD", "apikey": "fake-key"}
        return {"price": "456.78"}

    monkeypatch.setattr(CryptoService, "_request_json", fake_request)

    price = asyncio.run(service.twelvedata("BTC/USD"))
    assert price == pytest.approx(456.78)


def test_alpha_vantage_success(monkeypatch):
    service = CryptoService(cache_client=DummyCache())
    monkeypatch.setattr(Config, "ALPHA_VANTAGE_API_KEY", "alpha-key", raising=False)

    async def fake_request(self, url, *, session=None, params=None, **kwargs):
        assert params["from_currency"] == "BTC"
        return {
            "Realtime Currency Exchange Rate": {
                "5. Exchange Rate": "34567.89",
            }
        }

    monkeypatch.setattr(CryptoService, "_request_json", fake_request)

    price = asyncio.run(service.alpha_vantage("BTC"))
    assert price == pytest.approx(34567.89)


def test_get_price_uses_cache(monkeypatch):
    service = CryptoService(cache_client=DummyCache())

    async def coingecko_success(symbol):
        return 101.5

    async def fail_provider(symbol):
        pytest.fail("No debería llamarse a este proveedor cuando existe caché")

    monkeypatch.setattr(service, "coingecko", coingecko_success)
    monkeypatch.setattr(service, "binance", fail_provider)
    monkeypatch.setattr(service, "coinmarketcap", fail_provider)

    price = asyncio.run(service.get_price("btc"))
    assert price == pytest.approx(101.5)

    async def coingecko_fail(symbol):
        pytest.fail("No debería llamarse a CoinGecko tras cachear el resultado")

    monkeypatch.setattr(service, "coingecko", coingecko_fail)

    cached_price = asyncio.run(service.get_price("btc"))
    assert cached_price == pytest.approx(101.5)


def test_get_price_retries_and_fallback(monkeypatch):
    service = CryptoService(cache_client=DummyCache())
    service.RETRY_ATTEMPTS = 2
    service.RETRY_BACKOFF = 0

    attempts = {"coingecko": 0, "binance": 0}

    async def failing_coingecko(symbol):
        attempts["coingecko"] += 1
        raise aiohttp.ClientError("network down")

    async def binance_success(symbol):
        attempts["binance"] += 1
        return 123.45

    async def coinmarketcap_fail(symbol):
        pytest.fail("No debería llamarse a CoinMarketCap si Binance tiene éxito")

    monkeypatch.setattr(service, "coingecko", failing_coingecko)
    monkeypatch.setattr(service, "binance", binance_success)
    monkeypatch.setattr(service, "coinmarketcap", coinmarketcap_fail)

    price = asyncio.run(service.get_price("eth"))

    assert price == pytest.approx(123.45)
    assert attempts["coingecko"] == service.RETRY_ATTEMPTS
    assert attempts["binance"] == 1


def test_get_price_falls_back_to_coinmarketcap(monkeypatch):
    service = CryptoService(cache_client=DummyCache())
    service.RETRY_ATTEMPTS = 1
    service.RETRY_BACKOFF = 0

    async def coingecko_none(symbol):
        return None

    async def binance_none(symbol):
        return None

    coinmarketcap_calls = 0

    async def coinmarketcap_success(symbol):
        nonlocal coinmarketcap_calls
        coinmarketcap_calls += 1
        return 55.5

    monkeypatch.setattr(service, "coingecko", coingecko_none)
    monkeypatch.setattr(service, "binance", binance_none)
    monkeypatch.setattr(service, "coinmarketcap", coinmarketcap_success)

    price = asyncio.run(service.get_price("ltc"))

    assert price == pytest.approx(55.5)
    assert coinmarketcap_calls == 1


def test_crypto_endpoint_success(monkeypatch):
    async def fake_get_price(symbol):
        return 123.45

    async def fake_binance(symbol):
        return None

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)
    monkeypatch.setattr(market_service, "get_binance_price", fake_binance)

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        monkeypatch.setattr(
            alt_module.market_service.crypto_service, "get_price", fake_get_price
        )
        monkeypatch.setattr(
            alt_module.market_service, "get_binance_price", fake_binance
        )

    body = asyncio.run(get_crypto("BTC"))
    assert body["symbol"] == "BTC"
    assert body["price"] == 123.45


def test_crypto_endpoint_not_found(monkeypatch):
    async def fake_get_price(symbol):
        return None

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)
    monkeypatch.setattr(
        market_service, "get_binance_price", AsyncMock(return_value=None)
    )

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        monkeypatch.setattr(
            alt_module.market_service.crypto_service, "get_price", fake_get_price
        )
        monkeypatch.setattr(
            alt_module.market_service,
            "get_binance_price",
            AsyncMock(return_value=None),
        )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(get_crypto("UNKNOWN"))

    assert excinfo.value.status_code == 404
    assert "No se encontró" in excinfo.value.detail


def test_crypto_endpoint_failure(monkeypatch):
    async def fake_get_price(symbol):
        raise RuntimeError("boom")

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)
    monkeypatch.setattr(
        market_service, "get_binance_price", AsyncMock(return_value=None)
    )

    alt_module = sys.modules.get("services.market_service")
    if alt_module is not None:
        monkeypatch.setattr(
            alt_module.market_service.crypto_service, "get_price", fake_get_price
        )
        monkeypatch.setattr(
            alt_module.market_service,
            "get_binance_price",
            AsyncMock(return_value=None),
        )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(get_crypto("ETH"))

    assert excinfo.value.status_code == 502
