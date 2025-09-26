import asyncio
import os
import sys
from typing import Any, Dict

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest

from backend.services.forex_service import ForexService
from backend.utils.config import Config


class DummyCache:
    def __init__(self):
        self.values: Dict[str, Any] = {}

    async def get(self, key: str):
        return self.values.get(key.lower())

    async def set(self, key: str, value: Any, ttl: Any = None):  # noqa: ARG002
        self.values[key.lower()] = value


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def restore_config():
    original_td = Config.TWELVEDATA_API_KEY
    original_av = Config.ALPHA_VANTAGE_API_KEY
    yield
    Config.TWELVEDATA_API_KEY = original_td
    Config.ALPHA_VANTAGE_API_KEY = original_av


def make_service(monkeypatch, return_map):
    service = ForexService(
        cache_client=DummyCache(),
        session_factory=lambda timeout=None: DummySession(),
    )

    async def fake_call(self, handler, session, symbol, source_name):  # noqa: ANN001
        result = return_map.get(source_name)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(ForexService, "_call_with_retries", fake_call)
    return service


def test_forex_service_prefers_twelvedata(monkeypatch):
    Config.TWELVEDATA_API_KEY = "test"
    Config.ALPHA_VANTAGE_API_KEY = "alpha"
    service = make_service(
        monkeypatch,
        {
            "Twelve Data": {"price": 1.2345, "change": 0.5},
            "Yahoo Finance": {"price": 1.0, "change": 0.1},
            "Alpha Vantage": {"price": 0.5, "change": 0.05},
        },
    )

    result = asyncio.run(service.get_quote("eurusd"))
    assert result == {
        "symbol": "EUR/USD",
        "price": 1.2345,
        "change": 0.5,
        "source": "Twelve Data",
    }


def test_forex_service_fallback_to_yahoo(monkeypatch):
    Config.TWELVEDATA_API_KEY = None
    Config.ALPHA_VANTAGE_API_KEY = None
    service = make_service(
        monkeypatch,
        {
            "Twelve Data": None,
            "Yahoo Finance": {"price": 1.1, "change": None},
        },
    )

    result = asyncio.run(service.get_quote("GBP/JPY"))
    assert result == {
        "symbol": "GBP/JPY",
        "price": 1.1,
        "change": None,
        "source": "Yahoo Finance",
    }


def test_forex_service_uses_cache(monkeypatch):
    Config.TWELVEDATA_API_KEY = "test"
    Config.ALPHA_VANTAGE_API_KEY = "alpha"
    calls = {"count": 0}

    async def fake_call(self, handler, session, symbol, source_name):  # noqa: ANN001
        calls["count"] += 1
        return {"price": 2.0, "change": 0.1}

    service = ForexService(
        cache_client=DummyCache(),
        session_factory=lambda timeout=None: DummySession(),
    )
    monkeypatch.setattr(ForexService, "_call_with_retries", fake_call)

    first = asyncio.run(service.get_quote("xauusd"))
    second = asyncio.run(service.get_quote("XAUUSD"))

    assert first == second
    assert calls["count"] == 1


def test_forex_service_uses_alpha_vantage(monkeypatch):
    Config.TWELVEDATA_API_KEY = None
    Config.ALPHA_VANTAGE_API_KEY = "alpha"
    service = make_service(
        monkeypatch,
        {
            "Twelve Data": None,
            "Alpha Vantage": {"price": 1.5, "change": 0.2},
            "Yahoo Finance": None,
        },
    )

    result = asyncio.run(service.get_quote("usdbrl"))
    assert result == {
        "symbol": "USD/BRL",
        "price": 1.5,
        "change": 0.2,
        "source": "Alpha Vantage",
    }
