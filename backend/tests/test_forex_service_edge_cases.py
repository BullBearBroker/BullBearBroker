import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from backend.services.forex_service import ForexService
from backend.utils.config import Config


class DummyCache:
    def __init__(self) -> None:
        self.values: Dict[str, Any] = {}

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
    original_td = Config.TWELVEDATA_API_KEY
    original_av = Config.ALPHA_VANTAGE_API_KEY
    yield
    Config.TWELVEDATA_API_KEY = original_td
    Config.ALPHA_VANTAGE_API_KEY = original_av


@pytest.mark.asyncio
async def test_get_quote_falls_back_after_timeouts(monkeypatch):
    Config.TWELVEDATA_API_KEY = "td-key"
    Config.ALPHA_VANTAGE_API_KEY = "av-key"

    service = ForexService(
        cache_client=DummyCache(),
        session_factory=lambda timeout=None: DummySession(),
    )

    twelvedata_mock = AsyncMock(
        side_effect=[asyncio.TimeoutError()] * ForexService.RETRY_ATTEMPTS
    )
    alpha_mock = AsyncMock(
        side_effect=[KeyError("bad payload")] * ForexService.RETRY_ATTEMPTS
    )
    yahoo_mock = AsyncMock(return_value={"price": 1.5, "change": 0.02})

    monkeypatch.setattr(service, "_fetch_twelvedata", twelvedata_mock)
    monkeypatch.setattr(service, "_fetch_alpha_vantage", alpha_mock)
    monkeypatch.setattr(service, "_fetch_yahoo_finance", yahoo_mock)
    service.apis[0]["callable"] = twelvedata_mock
    service.apis[1]["callable"] = alpha_mock
    service.apis[2]["callable"] = yahoo_mock
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = await service.get_quote("eurusd")

    assert result == {
        "symbol": "EUR/USD",
        "price": 1.5,
        "change": 0.02,
        "source": "Yahoo Finance",
        "sources": ["Twelve Data", "Alpha Vantage", "Yahoo Finance"],
    }

    assert twelvedata_mock.await_count == service.RETRY_ATTEMPTS
    assert alpha_mock.await_count == service.RETRY_ATTEMPTS
    yahoo_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_cached_result_after_fallback(monkeypatch):
    Config.TWELVEDATA_API_KEY = "td-key"
    Config.ALPHA_VANTAGE_API_KEY = "av-key"

    service = ForexService(
        cache_client=DummyCache(),
        session_factory=lambda timeout=None: DummySession(),
    )

    twelvedata_mock = AsyncMock(
        side_effect=[asyncio.TimeoutError()] * ForexService.RETRY_ATTEMPTS
    )
    alpha_mock = AsyncMock(return_value={"price": 2.0, "change": None})

    monkeypatch.setattr(service, "_fetch_twelvedata", twelvedata_mock)
    monkeypatch.setattr(service, "_fetch_alpha_vantage", alpha_mock)
    service.apis[0]["callable"] = twelvedata_mock
    service.apis[1]["callable"] = alpha_mock
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    first = await service.get_quote("gbpjpy")
    second = await service.get_quote("GBPJPY")

    assert first == second
    assert first["source"] == "Alpha Vantage"
    assert first["sources"] == ["Twelve Data", "Alpha Vantage"]
    assert twelvedata_mock.await_count == service.RETRY_ATTEMPTS
    assert alpha_mock.await_count == 1


@pytest.mark.asyncio
async def test_get_quote_returns_none_when_all_fail(monkeypatch):
    Config.TWELVEDATA_API_KEY = "td-key"
    Config.ALPHA_VANTAGE_API_KEY = "av-key"

    service = ForexService(
        cache_client=DummyCache(),
        session_factory=lambda timeout=None: DummySession(),
    )

    failure = AsyncMock(return_value=None)
    monkeypatch.setattr(service, "_call_with_retries", failure)

    result = await service.get_quote("xauusd")

    assert result is None
    assert failure.await_count == 3


@pytest.mark.asyncio
async def test_fetch_alpha_vantage_invalid_symbol_raises_value_error(monkeypatch):
    Config.ALPHA_VANTAGE_API_KEY = "av-key"
    service = ForexService(
        cache_client=DummyCache(),
        session_factory=lambda timeout=None: DummySession(),
    )

    with pytest.raises(ValueError):
        await service._fetch_alpha_vantage(None, "USD")
