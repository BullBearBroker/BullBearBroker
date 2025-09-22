import json
import os
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import pytest
from aiohttp import ClientError

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.crypto_service import CryptoService  # noqa: E402


class FakeRedis:
    def __init__(self) -> None:
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        self.store[key] = value


def test_get_price_returns_cached_value():
    async def runner():
        redis_client = FakeRedis()
        cached_payload = {
            "symbol": "BTC",
            "price": 12345.0,
            "source": "median",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await redis_client.set("crypto:price:BTC", json.dumps(cached_payload), ex=30)

        service = CryptoService(redis_client=redis_client, cache_ttl=30)

        calls = {"count": 0}

        async def fail_fetch(_symbol: str):  # pragma: no cover - should not run
            calls["count"] += 1
            raise AssertionError("External API should not be called when cache is hit")

        service.apis = {
            "primary": ("coingecko", fail_fetch),
            "secondary": ("binance", fail_fetch),
            "fallback": ("coinmarketcap", fail_fetch),
        }

        result = await service.get_price("btc")

        assert result is not None
        assert result["price"] == cached_payload["price"]
        assert result["source"] == "cache"
        assert calls["count"] == 0

    asyncio.run(runner())


def test_get_price_handles_errors_and_aggregates():
    async def runner():
        service = CryptoService(redis_client=None)

        async def failing_source(_symbol: str):
            raise ClientError("boom")

        async def valid_source(_symbol: str):
            return 32000.0

        async def invalid_source(_symbol: str):
            return -10

        service.apis = {
            "primary": ("coingecko", failing_source),
            "secondary": ("binance", valid_source),
            "fallback": ("coinmarketcap", invalid_source),
        }

        result = await service.get_price("eth")

        assert result is not None
        assert result["symbol"] == "ETH"
        assert result["price"] == pytest.approx(32000.0)
        assert result["source"] == "binance"
        assert "timestamp" in result

    asyncio.run(runner())
