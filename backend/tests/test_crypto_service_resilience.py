import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.services.crypto_service import CryptoService
from backend.utils import cache as cache_module


class InMemoryCache:
    def __init__(self) -> None:
        self.data = {}

    async def get(self, key):  # noqa: D401 - simple proxy
        return self.data.get(key)

    async def set(self, key, value, ttl=None):  # noqa: D401 - simple proxy
        self.data[key] = value


@pytest.fixture(autouse=True)
def disable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module.Config, "REDIS_URL", None, raising=False)


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


@pytest.fixture()
def service(monkeypatch: pytest.MonkeyPatch) -> CryptoService:
    monkeypatch.setattr(CryptoService, "RETRY_ATTEMPTS", 2, raising=False)
    monkeypatch.setattr(CryptoService, "RETRY_BACKOFF", 0.01, raising=False)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return CryptoService(cache_client=InMemoryCache())


@pytest.mark.anyio
async def test_binance_empty_payload_falls_back_to_coinmarketcap(
    service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "coingecko", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "binance", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "coinmarketcap", AsyncMock(return_value=32100.5))
    monkeypatch.setattr(service, "twelvedata", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "alpha_vantage", AsyncMock(return_value=None))

    price = await service.get_price("BTCUSDT")
    assert price == 32100.5


@pytest.mark.anyio
async def test_incomplete_payload_returns_none(
    service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_coinmarketcap(symbol: str):  # noqa: ANN001 - helper
        raise KeyError("price missing")

    monkeypatch.setattr(service, "coingecko", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "binance", AsyncMock(return_value=None))
    monkeypatch.setattr(
        service, "coinmarketcap", AsyncMock(side_effect=broken_coinmarketcap)
    )
    monkeypatch.setattr(service, "twelvedata", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "alpha_vantage", AsyncMock(return_value=None))

    assert await service.get_price("ETHUSDT") is None


@pytest.mark.anyio
async def test_cache_hit_skips_provider_calls(
    service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = InMemoryCache()
    await cache.set("BTC", 20000.0)
    service.cache = cache

    provider = AsyncMock(return_value=123.0)
    monkeypatch.setattr(service, "coingecko", provider)

    result = await service.get_price("BTC")
    assert result == 20000.0
    provider.assert_not_awaited()


@pytest.mark.anyio
async def test_timeout_triggers_fallback_chain(
    service: CryptoService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    coingecko = AsyncMock(side_effect=TimeoutError())
    binance = AsyncMock(side_effect=ValueError("down"))
    coinmarketcap = AsyncMock(return_value=None)
    twelvedata = AsyncMock(return_value=15.0)

    monkeypatch.setattr(service, "coingecko", coingecko)
    monkeypatch.setattr(service, "binance", binance)
    monkeypatch.setattr(service, "coinmarketcap", coinmarketcap)
    monkeypatch.setattr(service, "twelvedata", twelvedata)
    monkeypatch.setattr(service, "alpha_vantage", AsyncMock(return_value=None))

    price = await service.get_price("ADAUSDT")
    assert price == 15.0
    assert coingecko.await_count == 2
    assert binance.await_count == 2
    assert twelvedata.await_count == 1
