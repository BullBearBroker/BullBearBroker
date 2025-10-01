from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.tests._dependency_stubs import ensure as ensure_test_dependencies

ensure_test_dependencies()

from backend.main import app
from backend.routers import news as news_router


class StubNewsService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_latest_news(self, limit: int) -> list[dict]:
        self.calls.append(f"latest:{limit}")
        return []

    async def get_crypto_headlines(self, limit: int) -> list[dict]:
        self.calls.append(f"crypto:{limit}")
        return [
            {
                "title": None,
                "url": "https://example.com/corrupted",
                "published_at": "2024-01-01T00:00:00Z",
                "summary": None,
            },
            {
                "title": "Valid entry",
                "url": "https://example.com/valid",
                "published_at": "2024-01-02T00:00:00Z",
                "summary": "ok",
            },
        ]


@pytest.fixture()
def stub_service(monkeypatch: pytest.MonkeyPatch) -> StubNewsService:
    service = StubNewsService()
    monkeypatch.setattr(news_router, "news_service", service)
    return service


@pytest_asyncio.fixture()
async def client() -> AsyncClient:  # type: ignore[name-defined]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_latest_news_returns_controlled_empty_list(
    client: AsyncClient, stub_service: StubNewsService
) -> None:
    response = await client.get("/api/news/latest")
    assert response.status_code == 404
    assert response.json()["detail"].startswith("No hay noticias")
    assert stub_service.calls == ["latest:20"]


@pytest.mark.asyncio
async def test_corrupted_provider_payload_is_handled(
    client: AsyncClient, stub_service: StubNewsService
) -> None:
    response = await client.get("/api/news/crypto")
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "crypto"
    assert len(payload["articles"]) == 2
    assert stub_service.calls[-1] == "crypto:10"
