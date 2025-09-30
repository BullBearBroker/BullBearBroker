import os
import sys
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/testdb")

from backend.main import app  # noqa: E402
from backend.services.market_service import market_service  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_history_endpoint_returns_payload(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    sample = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "source": "Binance",
        "values": [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
        ],
    }

    mock_get = AsyncMock(return_value=sample)
    monkeypatch.setattr(market_service, "get_historical_ohlc", mock_get)
    monkeypatch.setattr(
        "backend.routers.markets.market_service.get_historical_ohlc", mock_get
    )

    response = await client.get("/api/markets/history/BTCUSDT", params={"interval": "1h", "limit": 50})

    assert response.status_code == 200
    assert response.json() == sample
    mock_get.assert_awaited_with("BTCUSDT", interval="1h", limit=50, market="auto")


@pytest.mark.asyncio
async def test_history_endpoint_handles_not_found(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    mock_get = AsyncMock(side_effect=ValueError("sin datos"))
    monkeypatch.setattr(market_service, "get_historical_ohlc", mock_get)
    monkeypatch.setattr(
        "backend.routers.markets.market_service.get_historical_ohlc", mock_get
    )

    response = await client.get("/api/markets/history/ETHUSDT")

    assert response.status_code == 404
    assert "sin datos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_history_endpoint_handles_provider_failure(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    mock_get = AsyncMock(side_effect=RuntimeError("binance caido"))
    monkeypatch.setattr(market_service, "get_historical_ohlc", mock_get)
    monkeypatch.setattr(
        "backend.routers.markets.market_service.get_historical_ohlc", mock_get
    )

    response = await client.get("/api/markets/history/AAPL")

    assert response.status_code == 502
    assert "binance caido" in response.json()["detail"]
