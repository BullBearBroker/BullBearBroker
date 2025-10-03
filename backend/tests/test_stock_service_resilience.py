import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.services.stock_service import StockService
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


@pytest.fixture
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


@pytest.fixture()
def service(monkeypatch: pytest.MonkeyPatch) -> StockService:
    monkeypatch.setattr(StockService, "RETRY_ATTEMPTS", 2, raising=False)
    monkeypatch.setattr(StockService, "RETRY_BACKOFF", 0.01, raising=False)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return StockService(cache_client=InMemoryCache())


@pytest.mark.anyio
async def test_get_price_skips_corrupt_payload_and_falls_back(
    service: StockService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service, "_fetch_alpha_vantage", AsyncMock(side_effect=KeyError("price"))
    )
    monkeypatch.setattr(
        service, "_fetch_twelvedata", AsyncMock(side_effect=ValueError("bad data"))
    )
    monkeypatch.setattr(
        service,
        "_fetch_yahoo_finance",
        AsyncMock(return_value={"price": 120.5, "change": 1.2}),
    )

    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
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

    result = await service.get_price("AAPL")
    assert result == {"price": 120.5, "change": 1.2, "source": "Yahoo Finance"}


@pytest.mark.anyio
async def test_missing_api_keys_use_open_provider(
    service: StockService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service,
        "_fetch_yahoo_finance",
        AsyncMock(return_value={"price": 99.0, "change": -0.5}),
    )

    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "",
            },
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
                "requires_key": True,
                "api_key": None,
            },
            {
                "name": "Yahoo Finance",
                "callable": service._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    result = await service.get_price("TSLA")
    assert result == {"price": 99.0, "change": -0.5, "source": "Yahoo Finance"}


@pytest.mark.anyio
async def test_all_providers_fail_returns_none(
    service: StockService, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = AsyncMock(side_effect=ValueError("fail"))
    monkeypatch.setattr(service, "_fetch_yahoo_finance", failing)

    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Alpha Vantage",
                "callable": failing,
                "requires_key": True,
                "api_key": "",
            },
            {
                "name": "Twelve Data",
                "callable": failing,
                "requires_key": True,
                "api_key": "",
            },
            {
                "name": "Yahoo Finance",
                "callable": failing,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    assert await service.get_price("NFLX") is None


@pytest.mark.anyio
async def test_non_numeric_payload_triggers_retry(
    service: StockService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _invalid(*args, **kwargs):  # noqa: ANN001 - helper for clarity
        raise TypeError("non numeric")

    monkeypatch.setattr(
        service, "_fetch_alpha_vantage", AsyncMock(side_effect=_invalid)
    )
    monkeypatch.setattr(
        service,
        "_fetch_twelvedata",
        AsyncMock(return_value={"price": 55.0, "change": 0.0}),
    )

    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": "key",
            },
            {
                "name": "Twelve Data",
                "callable": service._fetch_twelvedata,
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

    result = await service.get_price("MSFT")
    assert result == {"price": 55.0, "change": 0.0, "source": "Twelve Data"}


@pytest.mark.anyio
async def test_providers_without_api_keys_are_skipped(
    service: StockService, monkeypatch: pytest.MonkeyPatch
) -> None:
    skipped = AsyncMock()
    fallback = AsyncMock(return_value={"price": 88.0, "change": 1.5})

    monkeypatch.setattr(service, "_fetch_alpha_vantage", skipped)
    monkeypatch.setattr(service, "_fetch_yahoo_finance", fallback)

    monkeypatch.setattr(
        service,
        "apis",
        [
            {
                "name": "Alpha Vantage",
                "callable": service._fetch_alpha_vantage,
                "requires_key": True,
                "api_key": None,
            },
            {
                "name": "Yahoo Finance",
                "callable": service._fetch_yahoo_finance,
                "requires_key": False,
                "api_key": None,
            },
        ],
    )

    payload = await service.get_price("IBM")
    skipped.assert_not_awaited()
    fallback.assert_awaited_once()
    assert payload == {"price": 88.0, "change": 1.5, "source": "Yahoo Finance"}
