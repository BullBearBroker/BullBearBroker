import uuid
from dataclasses import dataclass
from typing import Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app
from backend.models import Base, User, PortfolioItem  # noqa: F401 - ensure table registration
from backend.routers import portfolio as portfolio_router
from backend.services.portfolio_service import PortfolioService


@dataclass
class DummyUser:
    id: uuid.UUID
    email: str


class DummyUserService:
    class InvalidTokenError(Exception):
        pass

    def __init__(self, user: DummyUser) -> None:
        self._user = user

    def get_current_user(self, token: str) -> DummyUser:
        if token != "valid-token":
            raise self.InvalidTokenError("Token inválido")
        return self._user


@pytest.fixture()
def sqlite_session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


@pytest.fixture()
def persisted_user(sqlite_session_factory: sessionmaker) -> DummyUser:
    with sqlite_session_factory() as session:
        user = User(email="user@example.com", password_hash="hashed")
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return DummyUser(id=user.id, email=user.email)


class StubPortfolioService(PortfolioService):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory=session_factory)
        self._prices = {"BTCUSDT": 50000.0, "AAPL": 180.0, "EURUSD": 1.1}

    async def _resolve_price(self, symbol: str) -> Optional[float]:
        return self._prices.get(symbol.strip().upper())


@pytest.fixture()
def configured_service(sqlite_session_factory: sessionmaker) -> PortfolioService:
    return StubPortfolioService(session_factory=sqlite_session_factory)


@pytest_asyncio.fixture()
async def client(
    configured_service: PortfolioService,
    persisted_user: DummyUser,
    monkeypatch: pytest.MonkeyPatch,
):
    dummy_user_service = DummyUserService(persisted_user)
    monkeypatch.setattr(portfolio_router, "user_service", dummy_user_service)
    monkeypatch.setattr(
        portfolio_router, "InvalidTokenError", DummyUserService.InvalidTokenError
    )
    monkeypatch.setattr(portfolio_router, "USER_SERVICE_ERROR", None)
    monkeypatch.setattr(portfolio_router, "portfolio_service", configured_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio()
async def test_portfolio_crud_and_summary(
    client: AsyncClient,
):
    headers = {"Authorization": "Bearer valid-token"}

    create_one = await client.post(
        "/api/portfolio", json={"symbol": "btcUSDT", "amount": 0.5}, headers=headers
    )
    assert create_one.status_code == 201
    first_id = create_one.json()["id"]

    create_two = await client.post(
        "/api/portfolio", json={"symbol": "AAPL", "amount": 10}, headers=headers
    )
    assert create_two.status_code == 201

    response = await client.get("/api/portfolio", headers=headers)
    assert response.status_code == 200
    payload = response.json()

    assert pytest.approx(payload["total_value"], rel=1e-3) == 26800.0
    assert len(payload["items"]) == 2

    btc_entry = next(item for item in payload["items"] if item["symbol"] == "BTCUSDT")
    assert btc_entry["price"] == 50000.0
    assert pytest.approx(btc_entry["value"], rel=1e-6) == 25000.0

    delete_resp = await client.delete(f"/api/portfolio/{first_id}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["id"] == first_id

    updated = await client.get("/api/portfolio", headers=headers)
    assert updated.status_code == 200
    remaining = updated.json()
    assert len(remaining["items"]) == 1
    assert remaining["items"][0]["symbol"] == "AAPL"
    assert pytest.approx(remaining["total_value"], rel=1e-3) == 1800.0


@pytest.mark.asyncio()
async def test_portfolio_export_returns_csv(client: AsyncClient) -> None:
    headers = {"Authorization": "Bearer valid-token"}

    await client.post(
        "/api/portfolio",
        json={"symbol": "BTCUSDT", "amount": 1},
        headers=headers,
    )

    response = await client.get("/api/portfolio/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "BTCUSDT" in response.text


@pytest.mark.asyncio()
async def test_portfolio_import_creates_items_and_reports_errors(
    client: AsyncClient,
) -> None:
    headers = {"Authorization": "Bearer valid-token"}

    payload = "symbol,amount\nETHUSDT,2\n,0\nAAPL,not-a-number\n"
    response = await client.post(
        "/api/portfolio/import",
        headers=headers,
        files={"file": ("portfolio.csv", payload, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert any(error["row"] == 3 for error in body["errors"])
    assert any("numérica" in error["message"] for error in body["errors"])

    listing = await client.get("/api/portfolio", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert any(item["symbol"] == "ETHUSDT" for item in items)
