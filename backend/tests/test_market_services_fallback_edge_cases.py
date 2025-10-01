from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

from backend.services.crypto_service import CryptoService
from backend.services.forex_service import ForexService
from backend.services.stock_service import StockService
from backend.utils.config import Config


@pytest.fixture(autouse=True)
def restore_config() -> None:
    original_td = Config.TWELVEDATA_API_KEY
    original_alpha = Config.ALPHA_VANTAGE_API_KEY
    original_cmc = getattr(Config, "COINMARKETCAP_API_KEY", None)
    try:
        yield
    finally:
        Config.TWELVEDATA_API_KEY = original_td
        Config.ALPHA_VANTAGE_API_KEY = original_alpha
        if hasattr(Config, "COINMARKETCAP_API_KEY"):
            Config.COINMARKETCAP_API_KEY = original_cmc


class DummyCache:
    def __init__(self) -> None:
        self.values: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        return self.values.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:  # noqa: ARG002
        self.values[key] = value


@pytest.mark.asyncio
async def test_crypto_service_falls_back_when_primary_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = DummyCache()
    service = CryptoService(cache_client=cache)

    call_order: list[str] = []

    async def fake_call(provider, symbol, name):  # noqa: ANN001
        call_order.append(name)
        if name == "CoinGecko":
            return None
        if name == "Binance":
            return 42.0
        return None

    monkeypatch.setattr(service, "_call_with_retries", fake_call)

    price = await service.get_price("BTCUSDT")

    assert price == 42.0
    assert call_order[:2] == ["CoinGecko", "Binance"]

    # Cached value avoids re-fetching
    second = await service.get_price("BTCUSDT")
    assert second == 42.0
    assert call_order == ["CoinGecko", "Binance"]


@pytest.mark.asyncio
async def test_forex_service_skips_providers_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    Config.TWELVEDATA_API_KEY = None
    Config.ALPHA_VANTAGE_API_KEY = None

    service = ForexService(cache_client=DummyCache(), session_factory=lambda timeout=None: AsyncMock())

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

    def fake_session_factory(timeout=None):  # noqa: ANN001
        return DummySession()

    service._session_factory = fake_session_factory

    async def fake_call(handler, session, symbol, source_name):  # noqa: ANN001
        if source_name == "Yahoo Finance":
            return {"price": 1.2, "change": 0.01}
        return None

    monkeypatch.setattr(service, "_call_with_retries", fake_call)

    result = await service.get_quote("EURUSD")

    assert result == {
        "symbol": "EUR/USD",
        "price": 1.2,
        "change": 0.01,
        "source": "Yahoo Finance",
        "sources": ["Yahoo Finance"],
    }


@pytest.mark.asyncio
async def test_stock_service_handles_corrupt_provider_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    Config.TWELVEDATA_API_KEY = ""
    Config.ALPHA_VANTAGE_API_KEY = ""

    cache = DummyCache()
    service = StockService(cache_client=cache, session_factory=lambda timeout=None: AsyncMock())

    async def fake_call(handler, session, symbol, source_name):  # noqa: ANN001
        if source_name == "Yahoo Finance":
            return {"price": 120.0, "change": 1.5}
        return {"price": "nan"}

    monkeypatch.setattr(service, "_call_with_retries", fake_call)

    result = await service.get_price("AAPL")

    assert result == {"price": 120.0, "change": 1.5, "source": "Yahoo Finance"}
    assert cache.values["AAPL"] == {"price": 120.0, "change": 1.5, "source": "Yahoo Finance"}
