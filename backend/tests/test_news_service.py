import pytest

from backend.services.news_service import NewsService


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_get_latest_news_merges_and_sorts(monkeypatch):
    service = NewsService()

    crypto_articles = [
        {"title": "Crypto 1", "published_at": "2024-05-01T10:00:00+00:00"},
        {"title": "Crypto 2", "published_at": "2024-05-01T09:00:00+00:00"},
    ]
    finance_articles = [
        {"title": "Finance 1", "published_at": "2024-05-02T08:00:00+00:00"}
    ]

    async def fake_crypto(limit: int):  # noqa: ANN001
        return crypto_articles[:limit]

    async def fake_finance(limit: int):  # noqa: ANN001
        return finance_articles[:limit]

    monkeypatch.setattr(service, "get_crypto_headlines", fake_crypto)
    monkeypatch.setattr(service, "get_finance_headlines", fake_finance)

    latest = await service.get_latest_news(limit=3)

    assert [item["title"] for item in latest] == [
        "Finance 1",
        "Crypto 1",
        "Crypto 2",
    ]


@pytest.mark.anyio
async def test_get_latest_news_handles_errors(monkeypatch):
    service = NewsService()

    async def crypto_fail(limit: int):  # noqa: ANN001
        raise RuntimeError("crypto down")

    async def finance_ok(limit: int):  # noqa: ANN001
        return [
            {
                "title": "Finance",
                "published_at": "2024-05-01T00:00:00+00:00",
                "url": "https://finance.example/article",
            }
        ]

    monkeypatch.setattr(service, "get_crypto_headlines", crypto_fail)
    monkeypatch.setattr(service, "get_finance_headlines", finance_ok)

    latest = await service.get_latest_news(limit=2)

    assert len(latest) == 1
    assert latest[0]["title"] == "Finance"
