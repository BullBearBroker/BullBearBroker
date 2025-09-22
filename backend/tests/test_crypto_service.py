import asyncio
import os
import sys
from typing import Any, Dict, List

import pytest

import aiohttp

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import HTTPException

from app.main import crypto_service, get_crypto
from services.crypto_service import CryptoService


class DummyCache:
    def __init__(self):
        self.values: Dict[str, Any] = {}

    async def get(self, key: str):
        return self.values.get(key.lower())

    async def set(self, key: str, value: Any, ttl: Any = None):  # noqa: ARG002 - ttl no se usa
        self.values[key.lower()] = value


def test_coingecko_symbol_resolution(monkeypatch):
    service = CryptoService(cache_client=DummyCache())

    expected_calls: List[Dict[str, Any]] = []

    async def fake_request(self, url: str, *, session=None, **kwargs):  # noqa: ANN001 - firma requerida para monkeypatch
        if not expected_calls:
            pytest.fail("Se realizaron más llamadas de las esperadas a _request_json")
        call = expected_calls.pop(0)
        assert url == call["url"]
        if "params" in call:
            assert kwargs.get("params") == call["params"]
        return call["response"]

    monkeypatch.setattr(CryptoService, "_request_json", fake_request)

    expected_calls.extend(
        [
            {
                "url": "https://api.coingecko.com/api/v3/search",
                "params": {"query": "BTC"},
                "response": {"coins": [{"id": "bitcoin", "symbol": "btc"}]},
            },
            {
                "url": "https://api.coingecko.com/api/v3/simple/price",
                "params": {"ids": "bitcoin", "vs_currencies": "usd"},
                "response": {"bitcoin": {"usd": 30123.45}},
            },
        ]
    )

    price = asyncio.run(service.coingecko("BTC"))
    assert price == pytest.approx(30123.45)
    assert not expected_calls

    expected_calls.extend(
        [
            {
                "url": "https://api.coingecko.com/api/v3/search",
                "params": {"query": "UNKNOWN"},
                "response": {"coins": []},
            }
        ]
    )

    missing_price = asyncio.run(service.coingecko("UNKNOWN"))
    assert missing_price is None
    assert not expected_calls


def test_binance_failure(monkeypatch):
    service = CryptoService(cache_client=DummyCache())

    async def fake_request(*args, **kwargs):  # noqa: ANN001 - firma requerida para monkeypatch
        raise aiohttp.ClientError("network down")

    monkeypatch.setattr(service, "_request_json", fake_request)

    result = asyncio.run(service.binance("BTC"))
    assert result is None


def test_coinmarketcap_invalid_response(monkeypatch):
    service = CryptoService(cache_client=DummyCache())

    async def fake_request(*args, **kwargs):  # noqa: ANN001 - firma requerida para monkeypatch
        return {"data": {"ETH": {"quote": {"USD": {}}}}}

    monkeypatch.setattr(service, "_request_json", fake_request)

    result = asyncio.run(service.coinmarketcap("BTC"))
    assert result is None


def test_crypto_endpoint_success(monkeypatch):
    async def fake_get_price(symbol):  # noqa: ANN001 - firma requerida para monkeypatch
        return 123.45

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)

    body = asyncio.run(get_crypto("BTC"))
    assert body["symbol"] == "BTC"
    assert body["price"] == 123.45


def test_crypto_endpoint_not_found(monkeypatch):
    async def fake_get_price(symbol):  # noqa: ANN001 - firma requerida para monkeypatch
        return None

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(get_crypto("UNKNOWN"))

    assert excinfo.value.status_code == 404


def test_crypto_endpoint_failure(monkeypatch):
    async def fake_get_price(symbol):  # noqa: ANN001 - firma requerida para monkeypatch
        raise RuntimeError("boom")

    monkeypatch.setattr(crypto_service, "get_price", fake_get_price)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(get_crypto("ETH"))

    assert excinfo.value.status_code == 502
