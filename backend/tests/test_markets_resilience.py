from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app  # noqa: E402
from backend.routers import markets as markets_router  # noqa: E402


@pytest_asyncio.fixture()
async def client() -> AsyncClient:  # type: ignore[name-defined]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_crypto_prices_returns_404_for_unknown_symbol(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_price(symbol: str) -> None:  # noqa: ANN001
        await asyncio.sleep(0)
        return None

    monkeypatch.setattr(markets_router.market_service, "get_crypto_price", fake_price)

    response = await client.get(
        "/api/markets/crypto/prices",
        params={"symbols": "UNKNOWN"},
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("No se encontraron")


@pytest.mark.asyncio
async def test_stock_quotes_returns_404_for_unknown_symbol(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_price(symbol: str) -> None:  # noqa: ANN001
        await asyncio.sleep(0)
        return None

    monkeypatch.setattr(markets_router.market_service, "get_stock_price", fake_price)

    response = await client.get(
        "/api/markets/stocks/quotes",
        params={"symbols": "INVALID"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_forex_rates_returns_404_for_unknown_pair(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_quote(symbol: str) -> None:  # noqa: ANN001
        await asyncio.sleep(0)
        return None

    monkeypatch.setattr(markets_router.forex_service, "get_quote", fake_quote)

    response = await client.get(
        "/api/markets/forex/rates",
        params={"pairs": "ZZZYYY"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_crypto_endpoint_uses_binance_fallback(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def primary_failure(symbol: str) -> None:  # noqa: ANN001
        return None

    async def binance_fallback(symbol: str) -> dict:  # noqa: ANN001
        return {"price": "42100.5", "source": "Binance"}

    monkeypatch.setattr(
        markets_router.market_service.crypto_service,
        "get_price",
        primary_failure,
    )
    monkeypatch.setattr(
        markets_router.market_service, "get_binance_price", binance_fallback
    )

    response = await client.get("/api/markets/crypto/BTCUSDT")
    assert response.status_code == 200
    payload = response.json()
    assert payload["price"] == pytest.approx(42100.5)
    assert payload["source"].endswith("Binance")


@pytest.mark.asyncio
async def test_parse_symbols_rejects_corrupted_input(client: AsyncClient) -> None:
    response = await client.get(
        "/api/markets/crypto/prices",
        params={"symbols": " , , "},
    )

    assert response.status_code == 400
    assert "símbolo" in response.json()["detail"].lower()
