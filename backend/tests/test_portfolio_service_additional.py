from __future__ import annotations

import math
from uuid import uuid4

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
def portfolio_service(session_factory) -> PortfolioService:
    return PortfolioService(session_factory=session_factory)


@pytest.mark.asyncio()
async def test_empty_portfolio_returns_controlled_response(
    portfolio_service: PortfolioService,
):
    result = await portfolio_service.get_portfolio_overview(uuid4())
    assert result == {"items": [], "total_value": 0.0}


@pytest.mark.parametrize(
    "symbol, amount, expected",
    [
        ("   ", 1, "El símbolo es obligatorio"),
        ("BTC", 0, "La cantidad debe ser mayor que cero"),
        ("ETH", -5, "La cantidad debe ser mayor que cero"),
    ],
)
def test_create_item_invalid_inputs_raise(
    portfolio_service: PortfolioService, symbol: str, amount: float, expected: str
) -> None:
    with pytest.raises(ValueError) as exc_info:
        portfolio_service.create_item(uuid4(), symbol=symbol, amount=amount)
    assert expected in str(exc_info.value)


@pytest.mark.asyncio()
async def test_portfolio_overview_handles_atypical_prices(
    portfolio_service: PortfolioService, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid4()
    first = portfolio_service.create_item(user_id, symbol="XYZ", amount=2)
    second = portfolio_service.create_item(user_id, symbol="ABC", amount=3)

    prices = iter([-10.0, float("nan")])

    async def fake_resolve(symbol: str) -> float:
        return next(prices)

    monkeypatch.setattr(portfolio_service, "_resolve_price", fake_resolve)

    overview = await portfolio_service.get_portfolio_overview(user_id)

    assert overview["items"][0]["id"] == first.id
    assert overview["items"][0]["value"] == pytest.approx(-20.0)
    assert math.isnan(overview["items"][1]["value"])  # NaN propagated
    assert math.isnan(overview["total_value"])


@pytest.mark.asyncio()
async def test_portfolio_overview_reflects_latest_state(
    portfolio_service: PortfolioService, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid4()
    first = portfolio_service.create_item(user_id, symbol="AAA", amount=1)
    second = portfolio_service.create_item(user_id, symbol="BBB", amount=2)

    price_map = {"AAA": 10.0, "BBB": 20.0}

    async def price_lookup(symbol: str) -> float:
        return price_map[symbol.strip().upper()]

    monkeypatch.setattr(portfolio_service, "_resolve_price", price_lookup)

    initial = await portfolio_service.get_portfolio_overview(user_id)
    assert initial["total_value"] == pytest.approx(50.0)

    portfolio_service.delete_item(user_id, second.id)

    updated = await portfolio_service.get_portfolio_overview(user_id)
    assert {item["id"] for item in updated["items"]} == {first.id}
    assert updated["total_value"] == pytest.approx(10.0)

