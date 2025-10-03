from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app  # noqa: E402
from backend.routers import portfolio as portfolio_router  # noqa: E402


class DummyPortfolioService:
    def __init__(self) -> None:
        self.last_deleted: tuple[uuid.UUID, uuid.UUID] | None = None

    async def get_portfolio_overview(self, user_id: uuid.UUID) -> dict:
        return {"items": [], "total_value": 0.0}

    def delete_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        self.last_deleted = (user_id, item_id)
        return False


def _override_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), email="test@example.com")


@pytest.fixture(autouse=True)
def _override_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _override_user()
    app.dependency_overrides[portfolio_router.get_current_user] = lambda: user
    service = DummyPortfolioService()
    monkeypatch.setattr(portfolio_router, "portfolio_service", service)
    yield
    app.dependency_overrides.pop(portfolio_router.get_current_user, None)


@pytest_asyncio.fixture()
async def client() -> AsyncClient:  # type: ignore[name-defined]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"symbol": "BTC", "amount": 0},
        {"symbol": "ETH", "amount": -1},
        {"symbol": " ", "amount": 1},
    ],
)
async def test_create_item_invalid_amount_or_symbol(
    client: AsyncClient, payload: dict
) -> None:
    response = await client.post("/api/portfolio", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_item_returns_404(client: AsyncClient) -> None:
    response = await client.delete(f"/api/portfolio/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_empty_portfolio_overview_returns_zeroes(client: AsyncClient) -> None:
    response = await client.get("/api/portfolio")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"items": [], "total_value": 0.0}
