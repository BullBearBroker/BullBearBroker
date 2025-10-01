from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

import backend.services.news_service as news_service_module
from backend.services.news_service import NewsService
from backend.utils.config import Config


@dataclass
class _StubCache:
    store: Dict[str, Any]

    async def get(self, key: str) -> Optional[Any]:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.store[key] = value


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> NewsService:
    instance = NewsService()
    instance.cache = _StubCache({})  # type: ignore[assignment]
    instance._session_factory = lambda **kwargs: _DummySession()  # type: ignore[assignment]
    return instance


@pytest.mark.anyio
async def test_crypto_headlines_fallbacks_to_newsapi(service: NewsService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "CRYPTOPANIC_API_KEY", "token", raising=False)
    monkeypatch.setattr(Config, "NEWSAPI_API_KEY", "token", raising=False)

    fallback_articles = [
        {
            "title": "NewsAPI article",
            "url": "https://news.example/item",
            "published_at": "2024-05-01T10:00:00+00:00",
            "summary": "",
        }
    ]

    monkeypatch.setattr(service, "_fetch_cryptopanic", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_fetch_newsapi", AsyncMock(return_value=fallback_articles))
    monkeypatch.setattr(
        service,
        "_call_with_retries",
        AsyncMock(side_effect=[[], fallback_articles]),
    )
    monkeypatch.setattr(service, "cache", _StubCache({}))

    articles = await service._get_articles(
        cache_namespace="crypto",
        limit=3,
        primary_fetcher=service._fetch_cryptopanic,
        fallback_query="crypto",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "NewsAPI article"
    assert articles[0]["url"] == "https://news.example/item"


@pytest.mark.anyio
async def test_finance_headlines_use_primary_when_available(service: NewsService, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "title": "Finfeed headline",
            "url": "https://finfeed.example/item",
            "published_at": "2024-05-02T12:00:00+00:00",
            "source": "Finfeed",
        }
    ]

    monkeypatch.setattr(Config, "FINFEED_API_KEY", "token", raising=False)
    monkeypatch.setattr(service, "_fetch_finfeed", AsyncMock(return_value=payload))
    monkeypatch.setattr(service, "_call_with_retries", AsyncMock(return_value=payload))
    monkeypatch.setattr(service, "cache", _StubCache({}))

    articles = await service._get_articles(
        cache_namespace="finance",
        limit=2,
        primary_fetcher=service._fetch_finfeed,
        fallback_query="finance",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Finfeed headline"
    assert articles[0]["source"] == "Finfeed"


@pytest.mark.anyio
async def test_get_latest_news_deduplicates_results(service: NewsService, monkeypatch: pytest.MonkeyPatch) -> None:
    async def crypto(_limit: int) -> List[Dict[str, Any]]:
        return [
            {
                "title": "Shared",
                "url": "https://example.com/shared",
                "published_at": "2024-05-01T09:00:00+00:00",
                "source": "Crypto",
                "summary": "",
            }
        ]

    async def finance(_limit: int) -> List[Dict[str, Any]]:
        return [
            {
                "title": "Shared",
                "url": "https://example.com/shared",
                "published_at": "2024-05-01T12:00:00+00:00",
                "source": "Finance",
                "summary": "",
            },
            {
                "title": "Unique",
                "url": "https://example.com/unique",
                "published_at": "2024-05-02T12:00:00+00:00",
                "source": "Finance",
                "summary": "",
            },
        ]

    monkeypatch.setattr(service, "get_crypto_headlines", crypto)
    monkeypatch.setattr(service, "get_finance_headlines", finance)

    latest = await service.get_latest_news(limit=5)
    urls = [item["url"] for item in latest]
    assert urls == [
        "https://example.com/unique",
        "https://example.com/shared",
    ]


@pytest.mark.anyio
async def test_get_articles_ignores_entries_without_title_or_date(service: NewsService, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_articles = [
        {"title": None, "published_at": "2024-05-01T00:00:00+00:00"},
        {"title": "Valid", "published_at": None},
        {
            "title": "Usable",
            "url": "https://example.com/usable",
            "published_at": "2024-05-01T01:00:00+00:00",
        },
    ]

    async def fake_call(handler, session, limit, **kwargs):  # noqa: ANN001
        return raw_articles

    monkeypatch.setattr(service, "_call_with_retries", fake_call)
    monkeypatch.setattr(service, "cache", _StubCache({}))
    monkeypatch.setattr(Config, "FINFEED_API_KEY", "token", raising=False)

    articles = await service._get_articles(
        cache_namespace="test",
        limit=5,
        primary_fetcher=service._fetch_finfeed,
        fallback_query="test",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Usable"


@pytest.mark.anyio
async def test_get_articles_returns_empty_when_all_sources_fail(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "CRYPTOPANIC_API_KEY", "token", raising=False)
    monkeypatch.setattr(Config, "NEWSAPI_API_KEY", "token", raising=False)

    call_mock = AsyncMock(side_effect=[[], []])
    monkeypatch.setattr(service, "_call_with_retries", call_mock)
    monkeypatch.setattr(service, "cache", _StubCache({}))

    articles = await service._get_articles(
        cache_namespace="crypto",
        limit=5,
        primary_fetcher=service._fetch_cryptopanic,
        fallback_query="crypto",
    )

    assert articles == []
    assert call_mock.await_count == 2


@pytest.mark.anyio
async def test_get_latest_news_keeps_most_recent_duplicate(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    latest_entry = {
        "title": "Shared",  # same identifier
        "url": "https://example.com/shared",
        "published_at": "2024-05-04T12:00:00+00:00",
        "source": "Crypto",
        "summary": "",
    }
    older_entry = {
        "title": "Shared",
        "url": "https://example.com/shared",
        "published_at": "2024-05-03T12:00:00+00:00",
        "source": "Finance",
        "summary": "",
    }

    async def crypto(_limit: int) -> List[Dict[str, Any]]:
        return [latest_entry]

    async def finance(_limit: int) -> List[Dict[str, Any]]:
        return [older_entry]

    monkeypatch.setattr(service, "get_crypto_headlines", crypto)
    monkeypatch.setattr(service, "get_finance_headlines", finance)

    results = await service.get_latest_news(limit=5)

    assert len(results) == 1
    assert results[0]["published_at"] == "2024-05-04T12:00:00+00:00"


@pytest.mark.anyio
async def test_get_articles_discards_corrupted_payload_without_source(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_articles = [
        {
            "title": None,
            "url": "https://example.com/bad",
            "published_at": "2024-05-01T00:00:00+00:00",
            "source": None,
            "summary": "",
        },
        {
            "title": "Valid",
            "url": "https://example.com/good",
            "published_at": "2024-05-01T01:00:00+00:00",
            "source": "Feed",
            "summary": "",
        },
    ]

    async def fake_call(handler, session, limit, **kwargs):  # noqa: ANN001
        return raw_articles

    monkeypatch.setattr(service, "_call_with_retries", fake_call)
    monkeypatch.setattr(service, "cache", _StubCache({}))
    monkeypatch.setattr(Config, "NEWSAPI_API_KEY", "token", raising=False)

    articles = await service._get_articles(
        cache_namespace="finance",
        limit=5,
        primary_fetcher=None,
        fallback_query="finance",
    )

    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/good"
