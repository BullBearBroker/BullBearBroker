from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services.stock_service import StockService
from backend.utils.config import Config


class DummyCache:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    async def get(self, key: str):
        return self.values.get(key.lower())

    async def set(self, key: str, value: Any, ttl: Any = None):  # noqa: ARG002
        self.values[key.lower()] = value


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False


@pytest.fixture(autouse=True)
def restore_config():
    original_twelve = Config.TWELVEDATA_API_KEY
    original_alpha = Config.ALPHA_VANTAGE_API_KEY
    yield
    Config.TWELVEDATA_API_KEY = original_twelve
    Config.ALPHA_VANTAGE_API_KEY = original_alpha


@pytest.mark.asyncio
async def test_fetch_yahoo_finance_with_corrupt_payload(monkeypatch):
    service = StockService(
        cache_client=DummyCache(), session_factory=lambda timeout=None: DummySession()
    )
    monkeypatch.setattr(service, "_fetch_json", AsyncMock(return_value={"chart": {}}))

    with pytest.raises(KeyError):
        await service._fetch_yahoo_finance(None, "AAPL")


@pytest.mark.asyncio
async def test_fetch_alpha_vantage_with_missing_quote(monkeypatch):
    Config.ALPHA_VANTAGE_API_KEY = "alpha-key"
    service = StockService(
        cache_client=DummyCache(), session_factory=lambda timeout=None: DummySession()
    )
    monkeypatch.setattr(service, "_fetch_json", AsyncMock(return_value={}))

    with pytest.raises(KeyError):
        await service._fetch_alpha_vantage(None, "MSFT")


@pytest.mark.asyncio
async def test_get_price_skips_providers_without_keys(monkeypatch):
    Config.TWELVEDATA_API_KEY = None
    Config.ALPHA_VANTAGE_API_KEY = None

    service = StockService(
        cache_client=DummyCache(), session_factory=lambda timeout=None: DummySession()
    )
    provider_mock = AsyncMock(return_value={"price": 123.45, "change": 1.5})
    monkeypatch.setattr(service, "_call_with_retries", provider_mock)

    result = await service.get_price("AAPL")

    assert result == {"price": 123.45, "change": 1.5, "source": "Yahoo Finance"}
    provider_mock.assert_awaited_once()
    called_handler, _, _, source_name = provider_mock.await_args.args
    assert source_name == "Yahoo Finance"
    assert called_handler is service.apis[-1]["callable"]


@pytest.mark.asyncio
async def test_get_price_returns_none_when_all_fail(monkeypatch):
    Config.TWELVEDATA_API_KEY = "td-key"
    Config.ALPHA_VANTAGE_API_KEY = "alpha-key"

    service = StockService(
        cache_client=DummyCache(), session_factory=lambda timeout=None: DummySession()
    )
    failure_mock = AsyncMock(side_effect=[None, None, None])
    monkeypatch.setattr(service, "_call_with_retries", failure_mock)

    result = await service.get_price("NFLX")

    assert result is None
    assert failure_mock.await_count == 3
    sources = [call.args[3] for call in failure_mock.await_args_list]
    assert sources == [api["name"] for api in service.apis]
