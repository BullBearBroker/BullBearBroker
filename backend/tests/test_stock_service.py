import asyncio
import os
import sys
from typing import Any

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.stock_service import StockService  # noqa: E402

from backend.utils.config import Config  # noqa: E402


class DummyCache:
    def __init__(self):
        self.values: dict[str, Any] = {}

    async def get(self, key: str):
        return self.values.get(key.lower())

    async def set(
        self, key: str, value: Any, ttl: Any = None
    ):  # noqa: ARG002 - ttl no se usa
        self.values[key.lower()] = value


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
        return False

    async def get(
        self, *args, **kwargs
    ):  # pragma: no cover - nunca se llama en los tests
        raise AssertionError("DummySession.get no debería ser llamado")


@pytest.fixture(autouse=True)
def restore_config():
    original_twelve = Config.TWELVEDATA_API_KEY
    original_alpha = Config.ALPHA_VANTAGE_API_KEY
    yield
    Config.TWELVEDATA_API_KEY = original_twelve
    Config.ALPHA_VANTAGE_API_KEY = original_alpha


def make_service(monkeypatch, return_map):
    service = StockService(
        cache_client=DummyCache(), session_factory=lambda timeout=None: DummySession()
    )

    async def fake_call(self, handler, session, symbol, source_name):  # noqa: ANN001
        result = return_map.get(source_name)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(StockService, "_call_with_retries", fake_call)
    return service


def test_stock_service_uses_twelvedata(monkeypatch):
    Config.TWELVEDATA_API_KEY = "test-key"
    Config.ALPHA_VANTAGE_API_KEY = "alpha-key"

    service = make_service(
        monkeypatch,
        {
            "Twelve Data": {"price": 101.25, "change": 1.5},
            "Yahoo Finance": None,
            "Alpha Vantage": None,
        },
    )

    result = asyncio.run(service.get_price("AAPL"))
    assert result == {"price": 101.25, "change": 1.5, "source": "Twelve Data"}


def test_stock_service_uses_yahoo_on_twelvedata_failure(monkeypatch):
    Config.TWELVEDATA_API_KEY = "test-key"
    Config.ALPHA_VANTAGE_API_KEY = "alpha-key"

    service = make_service(
        monkeypatch,
        {
            "Twelve Data": None,
            "Yahoo Finance": {"price": 99.87, "change": -0.3},
            "Alpha Vantage": None,
        },
    )

    result = asyncio.run(service.get_price("MSFT"))
    assert result == {"price": 99.87, "change": -0.3, "source": "Yahoo Finance"}


def test_stock_service_fallback_to_alpha_when_keys_missing(monkeypatch):
    Config.TWELVEDATA_API_KEY = None
    Config.ALPHA_VANTAGE_API_KEY = "alpha-key"

    service = make_service(
        monkeypatch,
        {
            "Twelve Data": None,
            "Yahoo Finance": None,
            "Alpha Vantage": {"price": 87.5, "change": 0.75},
        },
    )

    result = asyncio.run(service.get_price("TSLA"))
    assert result == {"price": 87.5, "change": 0.75, "source": "Alpha Vantage"}
