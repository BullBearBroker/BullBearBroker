import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.services.forex_service import ForexService
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
def service(monkeypatch: pytest.MonkeyPatch) -> ForexService:
    monkeypatch.setattr(ForexService, "RETRY_ATTEMPTS", 2, raising=False)
    monkeypatch.setattr(ForexService, "RETRY_BACKOFF", 0.01, raising=False)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return ForexService(cache_client=InMemoryCache())


@pytest.mark.anyio
async def test_twelvedata_failure_falls_back_to_yahoo(
    service: ForexService, monkeypatch: pytest.MonkeyPatch
) -> None:
    twelvedata = AsyncMock(side_effect=ValueError("down"))
    alphav = AsyncMock(side_effect=KeyError("price"))
    yahoo = AsyncMock(return_value={"price": 1.1234, "change": -0.001})

    monkeypatch.setattr(service, "_fetch_twelvedata", twelvedata)
    monkeypatch.setattr(service, "_fetch_alpha_vantage", alphav)
    monkeypatch.setattr(service, "_fetch_yahoo_finance", yahoo)
    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Yahoo Finance",
                "callable": service._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    quote = await service.get_quote("EURUSD")
    assert quote == {
        "symbol": "EUR/USD",
        "price": 1.1234,
        "change": -0.001,
        "source": "Yahoo Finance",
        "sources": ["Twelve Data", "Alpha Vantage", "Yahoo Finance"],
    }


@pytest.mark.anyio
async def test_corrupt_payload_returns_none(
    service: ForexService, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = AsyncMock(side_effect=TypeError("invalid"))
    monkeypatch.setattr(service, "_fetch_twelvedata", failing)
    monkeypatch.setattr(service, "_fetch_alpha_vantage", failing)
    monkeypatch.setattr(service, "_fetch_yahoo_finance", failing)
    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Yahoo Finance",
                "callable": service._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    assert await service.get_quote("GBPUSD") is None


@pytest.mark.anyio
async def test_all_providers_fail_returns_none(
    service: ForexService, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = AsyncMock(side_effect=ValueError("error"))
    monkeypatch.setattr(service, "_fetch_twelvedata", failing)
    monkeypatch.setattr(service, "_fetch_alpha_vantage", failing)
    monkeypatch.setattr(service, "_fetch_yahoo_finance", failing)
    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Yahoo Finance",
                "callable": service._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    assert await service.get_quote("USDJPY") is None


def test_invalid_symbol_raises_value_error(service: ForexService) -> None:
    with pytest.raises(ValueError):
        service._split_symbol("BAD")


@pytest.mark.anyio
async def test_timeout_in_primary_provider_falls_back(
    service: ForexService, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeout = AsyncMock(side_effect=TimeoutError())
    yahoo = AsyncMock(return_value={"price": 2.5, "change": 0.01})

    monkeypatch.setattr(service, "_fetch_twelvedata", timeout)
    monkeypatch.setattr(service, "_fetch_alpha_vantage", timeout)
    monkeypatch.setattr(service, "_fetch_yahoo_finance", yahoo)

    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Yahoo Finance",
                "callable": service._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    quote = await service.get_quote("AUDUSD")
    assert quote == {
        "symbol": "AUD/USD",
        "price": 2.5,
        "change": 0.01,
        "source": "Yahoo Finance",
        "sources": ["Twelve Data", "Alpha Vantage", "Yahoo Finance"],
    }
