from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

import backend.services.portfolio_service as portfolio_service
from backend.database import SessionLocal
from backend.models import Portfolio, Position, User

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def cleanup_db() -> None:
    yield
    with SessionLocal() as session:
        session.execute(delete(Position))
        session.execute(delete(Portfolio))
        session.execute(delete(User))
        session.commit()


@pytest.fixture()
def auth_context(dummy_user_service):
    user = dummy_user_service.create_user("user@example.com", "secure")
    token, _ = dummy_user_service.create_access_token(user)
    dummy_user_service.create_session(user.id, token=token)
    with SessionLocal() as session:
        session.merge(User(id=user.id, email=user.email, password_hash="hashed"))
        session.commit()
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture()
def secondary_user(dummy_user_service):
    other = dummy_user_service.create_user("other@example.com", "secure")
    token, _ = dummy_user_service.create_access_token(other)
    dummy_user_service.create_session(other.id, token=token)
    with SessionLocal() as session:
        session.merge(User(id=other.id, email=other.email, password_hash="hashed"))
        session.commit()
    return {"Authorization": f"Bearer {token}"}, other


async def _create_portfolio(
    client: AsyncClient, headers: dict[str, str], name: str = "Core"
) -> uuid.UUID:
    response = await client.post(
        "/api/portfolio",
        headers=headers,
        json={"name": name, "base_ccy": "USD"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == name
    assert payload["positions"] == []
    assert payload["totals"]["equity_value"] == 0.0
    return uuid.UUID(payload["id"])


async def test_create_and_list_portfolios(async_client: AsyncClient, auth_context):
    headers, _ = auth_context

    created_id = await _create_portfolio(async_client, headers)
    assert isinstance(created_id, uuid.UUID)

    listing = await async_client.get("/api/portfolio", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert len(body) == 1
    assert body[0]["id"] == str(created_id)
    assert body[0]["totals"]["equity_value"] == 0.0
    assert body[0]["metrics"] is None
    assert body[0]["risk"] is None


async def test_add_and_remove_positions(async_client: AsyncClient, auth_context):
    headers, _ = auth_context

    portfolio_id = await _create_portfolio(async_client, headers, name="Growth")

    add_first = await async_client.post(
        f"/api/portfolio/{portfolio_id}/positions",
        headers=headers,
        json={"symbol": "AAPL", "quantity": 2, "avg_price": 150},
    )
    assert add_first.status_code == 201
    first_id = add_first.json()["id"]

    add_second = await async_client.post(
        f"/api/portfolio/{portfolio_id}/positions",
        headers=headers,
        json={"symbol": "MSFT", "quantity": 1.5, "avg_price": 300},
    )
    assert add_second.status_code == 201

    detail = await async_client.get(f"/api/portfolio/{portfolio_id}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert {p["symbol"] for p in detail_body["positions"]} == {"AAPL", "MSFT"}

    delete_resp = await async_client.delete(
        f"/api/portfolio/positions/{first_id}", headers=headers
    )
    assert delete_resp.status_code == 204

    detail_after = await async_client.get(
        f"/api/portfolio/{portfolio_id}", headers=headers
    )
    assert detail_after.status_code == 200
    assert [p["symbol"] for p in detail_after.json()["positions"]] == ["MSFT"]


async def test_portfolio_detail_valuation(
    async_client: AsyncClient, auth_context, monkeypatch
):
    headers, _ = auth_context

    portfolio_id = await _create_portfolio(async_client, headers, name="Quant")

    await async_client.post(
        f"/api/portfolio/{portfolio_id}/positions",
        headers=headers,
        json={"symbol": "BTCUSDT", "quantity": 2, "avg_price": 90},
    )
    await async_client.post(
        f"/api/portfolio/{portfolio_id}/positions",
        headers=headers,
        json={"symbol": "ETHUSDT", "quantity": 5, "avg_price": 8},
    )

    class PriceStub:
        async def get_crypto_price(self, symbol: str):  # noqa: D401 - simple stub
            return None

        async def get_stock_price(self, symbol: str):
            prices = {
                "BTCUSDT": {"price": 100.0},
                "ETHUSDT": {"price": 10.0},
            }
            return prices.get(symbol)

    monkeypatch.setattr(portfolio_service, "market_service", PriceStub())

    detail = await async_client.get(f"/api/portfolio/{portfolio_id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()

    totals = payload["totals"]
    assert pytest.approx(totals["equity_value"], rel=1e-6) == 250.0
    assert pytest.approx(totals["pnl_abs"], rel=1e-6) == 30.0
    assert pytest.approx(totals["pnl_pct"], rel=1e-6) == 30 / 220
    assert payload["metrics"] is None
    assert payload["risk"] is None


async def test_portfolio_access_is_restricted(
    async_client: AsyncClient, auth_context, secondary_user
):
    headers_owner, _ = auth_context
    headers_intruder, _ = secondary_user

    portfolio_id = await _create_portfolio(async_client, headers_owner, name="Private")
    add_owner_position = await async_client.post(
        f"/api/portfolio/{portfolio_id}/positions",
        headers=headers_owner,
        json={"symbol": "TSLA", "quantity": 1, "avg_price": 100},
    )
    assert add_owner_position.status_code == 201
    position_id = add_owner_position.json()["id"]

    response = await async_client.get(
        f"/api/portfolio/{portfolio_id}", headers=headers_intruder
    )
    assert response.status_code == 404

    add_attempt = await async_client.post(
        f"/api/portfolio/{portfolio_id}/positions",
        headers=headers_intruder,
        json={"symbol": "TSLA", "quantity": 1, "avg_price": 100},
    )
    assert add_attempt.status_code == 404

    response_delete = await async_client.delete(
        f"/api/portfolio/positions/{position_id}", headers=headers_intruder
    )
    assert response_delete.status_code == 404
