import asyncio
import os
import sys
from typing import Any, Dict, List

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

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

    async def fake_request(self, url: str, **kwargs):  # noqa: ANN001 - firma requerida para monkeypatch
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
