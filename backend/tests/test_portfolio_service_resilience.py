import sys
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.services.portfolio_service import PortfolioService


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


@pytest.fixture()
def service(session_factory) -> PortfolioService:
    return PortfolioService(session_factory=session_factory)


def test_create_item_rejects_non_numeric_amount(service: PortfolioService) -> None:
    with pytest.raises(ValueError):
        service.create_item(uuid4(), symbol="AAPL", amount="abc")


@pytest.mark.anyio
async def test_overview_handles_missing_prices(service: PortfolioService) -> None:
    user_id = uuid4()
    first = service.create_item(user_id, symbol="AAA", amount=1)
    second = service.create_item(user_id, symbol="BBB", amount=2)

    async def resolve(symbol: str):  # noqa: ANN001
        return None

    service._resolve_price = resolve  # type: ignore[assignment]

    overview = await service.get_portfolio_overview(user_id)
    assert overview["items"][0]["id"] == first.id
    assert overview["items"][0]["value"] is None
    assert overview["items"][1]["id"] == second.id
    assert overview["total_value"] == 0.0


@pytest.mark.anyio
async def test_resolve_price_ignores_invalid_provider_payloads(service: PortfolioService, monkeypatch: pytest.MonkeyPatch) -> None:
    market = SimpleNamespace(
        get_crypto_price=AsyncMock(return_value={"price": "not-a-number"}),
        get_stock_price=AsyncMock(return_value={"price": 100.0}),
    )
    forex = SimpleNamespace(get_quote=AsyncMock(return_value={"price": "1.2"}))

    module = sys.modules["backend.services.portfolio_service"]
    monkeypatch.setattr(module, "market_service", market, raising=False)
    monkeypatch.setattr(module, "forex_service", forex, raising=False)

    price = await service._resolve_price("BTC")
    assert price == 100.0
    assert market.get_crypto_price.await_count == 1
    assert market.get_stock_price.await_count == 1


@pytest.mark.anyio
async def test_resolve_price_returns_none_when_all_sources_fail(service: PortfolioService, monkeypatch: pytest.MonkeyPatch) -> None:
    failing_async = AsyncMock(return_value={"price": "bad"})
    market = SimpleNamespace(
        get_crypto_price=AsyncMock(return_value={"price": None}),
        get_stock_price=failing_async,
    )
    forex = SimpleNamespace(get_quote=AsyncMock(return_value={"price": None}))

    module = sys.modules["backend.services.portfolio_service"]
    monkeypatch.setattr(module, "market_service", market, raising=False)
    monkeypatch.setattr(module, "forex_service", forex, raising=False)

    price = await service._resolve_price("EURUSD")
    assert price is None
