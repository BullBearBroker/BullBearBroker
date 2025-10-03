from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services.news_service import NewsService
from backend.utils.config import Config


@dataclass
class _StubCache:
    store: dict[str, Any]

    async def get(self, key: str) -> Any | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
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
async def test_crypto_headlines_fallbacks_to_newsapi(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch.setattr(
        service, "_fetch_newsapi", AsyncMock(return_value=fallback_articles)
    )
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
async def test_finance_headlines_use_primary_when_available(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
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
async def test_get_latest_news_deduplicates_results(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def crypto(_limit: int) -> list[dict[str, Any]]:
        return [
            {
                "title": "Shared",
                "url": "https://example.com/shared",
                "published_at": "2024-05-01T09:00:00+00:00",
                "source": "Crypto",
                "summary": "",
            }
        ]

    async def finance(_limit: int) -> list[dict[str, Any]]:
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
async def test_get_articles_ignores_entries_without_title_or_date(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
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
async def test_get_articles_deduplicates_same_title_and_timestamp(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = datetime(2024, 5, 5, 12, 0, tzinfo=UTC).isoformat()
    raw_articles = [
        {
            "title": "Duplicated headline",
            "url": None,
            "published_at": published,
            "summary": "Uno",
        },
        {
            "title": "Duplicated headline",
            "url": None,
            "published_at": published,
            "summary": "Dos",
        },
    ]

    async def fake_call(handler, session, limit, **kwargs):  # noqa: ANN001
        return raw_articles

    monkeypatch.setattr(service, "_call_with_retries", fake_call)
    monkeypatch.setattr(service, "cache", _StubCache({}))
    monkeypatch.setattr(Config, "FINFEED_API_KEY", "token", raising=False)

    articles = await service._get_articles(
        cache_namespace="finance",
        limit=5,
        primary_fetcher=service._fetch_finfeed,
        fallback_query="finance",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Duplicated headline"


@pytest.mark.anyio
async def test_get_articles_skips_blank_and_untitled_entries(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = datetime(2024, 5, 6, 12, 0, tzinfo=UTC).isoformat()
    raw_articles = [
        {"title": " ", "url": "https://example.com/space", "published_at": published},
        {
            "title": "Untitled",
            "url": "https://example.com/untitled",
            "published_at": published,
        },
        {
            "title": "Legible",
            "url": "https://example.com/ok",
            "published_at": published,
        },
    ]

    async def fake_call(handler, session, limit, **kwargs):  # noqa: ANN001
        return raw_articles

    monkeypatch.setattr(service, "_call_with_retries", fake_call)
    monkeypatch.setattr(service, "cache", _StubCache({}))
    monkeypatch.setattr(Config, "FINFEED_API_KEY", "token", raising=False)

    articles = await service._get_articles(
        cache_namespace="finance",
        limit=5,
        primary_fetcher=service._fetch_finfeed,
        fallback_query="finance",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Legible"


@pytest.mark.anyio
async def test_latest_news_skips_corrupted_source_payload(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_crypto(_limit: int) -> list[dict[str, Any]]:
        raise ValueError("crypto payload corrupt")

    async def finance_entries(_limit: int) -> list[dict[str, Any]]:
        return [
            {
                "title": "Fin válido",
                "url": "https://example.com/fin",
                "published_at": datetime(2024, 5, 7, 12, 0, tzinfo=UTC).isoformat(),
                "summary": "",
            }
        ]

    monkeypatch.setattr(service, "get_crypto_headlines", failing_crypto)
    monkeypatch.setattr(service, "get_finance_headlines", finance_entries)

    latest = await service.get_latest_news(limit=3)

    assert len(latest) == 1
    assert latest[0]["title"] == "Fin válido"


@pytest.mark.anyio
async def test_latest_news_merges_and_sorts_by_recency(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = datetime(2024, 5, 10, 12, 0, tzinfo=UTC)

    async def crypto(_limit: int) -> list[dict[str, Any]]:
        return [
            {
                "title": "Crypto reciente",
                "url": "https://example.com/crypto",
                "published_at": (base + timedelta(hours=1)).isoformat(),
                "summary": "",
            },
            {
                "title": "Crypto antiguo",
                "url": "https://example.com/crypto-old",
                "published_at": (base - timedelta(days=1)).isoformat(),
                "summary": "",
            },
        ]

    async def finance(_limit: int) -> list[dict[str, Any]]:
        return [
            {
                "title": "Finance medio",
                "url": "https://example.com/finance",
                "published_at": base.isoformat(),
                "summary": "",
            }
        ]

    monkeypatch.setattr(service, "get_crypto_headlines", crypto)
    monkeypatch.setattr(service, "get_finance_headlines", finance)

    latest = await service.get_latest_news(limit=3)
    ordered_titles = [item["title"] for item in latest]

    assert ordered_titles == [
        "Crypto reciente",
        "Finance medio",
        "Crypto antiguo",
    ]


@pytest.mark.anyio
async def test_fetch_cryptopanic_normalizes_results(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "results": [
            {
                "title": "Headline",
                "url": "https://example.com/post",
                "published_at": "2024-05-01T10:00:00+00:00",
                "body": "<b>Alert</b>",
                "source": {"title": "Crypto Blog"},
            }
        ]
    }

    async def fake_fetch_json(
        session, url, params=None, headers=None, source_name=None
    ):  # noqa: ANN001
        assert source_name == "CryptoPanic"
        return payload

    monkeypatch.setattr(service, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(Config, "CRYPTOPANIC_API_KEY", "token", raising=False)

    articles = await service._fetch_cryptopanic(None, 5)

    assert articles[0]["source"] == "Crypto Blog"
    assert articles[0]["summary"] == "Alert"


@pytest.mark.anyio
async def test_fetch_finfeed_supports_multiple_fields(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "data": [
            {
                "headline": "Finfeed Headline",
                "link": "https://example.com/fin",
                "published": "Wed, 01 May 2024 10:00:00 GMT",
                "description": "<p>Summary</p>",
            }
        ]
    }

    async def fake_fetch_json(
        session, url, params=None, headers=None, source_name=None
    ):  # noqa: ANN001
        assert source_name == "Finfeed"
        return payload

    monkeypatch.setattr(service, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(Config, "FINFEED_API_KEY", "token", raising=False)

    articles = await service._fetch_finfeed(None, 5)

    assert articles[0]["title"] == "Finfeed Headline"
    assert articles[0]["summary"] == "Summary"


@pytest.mark.anyio
async def test_fetch_newsapi_uses_domain_when_source_missing(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "articles": [
            {
                "title": "API headline",
                "url": "https://news.example/item",
                "publishedAt": "2024-05-01T12:00:00Z",
                "content": "<p>Body</p>",
                "source": {},
            }
        ]
    }

    async def fake_fetch_json(
        session, url, params=None, headers=None, source_name=None
    ):  # noqa: ANN001
        assert source_name == "NewsAPI"
        return payload

    monkeypatch.setattr(service, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(Config, "NEWSAPI_API_KEY", "token", raising=False)

    articles = await service._fetch_newsapi(None, 5, query="q")

    assert articles[0]["source"] == "news.example"


@pytest.mark.anyio
async def test_call_with_retries_eventually_succeeds(
    service: NewsService, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = {"count": 0}

    async def flaky_handler(session, limit, **kwargs):  # noqa: ANN001
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ValueError("temporary failure")
        return [{"title": "Ok", "published_at": "2024-05-01T00:00:00+00:00"}]

    monkeypatch.setattr(NewsService, "RETRY_BACKOFF", 0, raising=False)

    result = await service._call_with_retries(flaky_handler, None, 5)

    assert attempts["count"] == 3
    assert result[0]["title"] == "Ok"
    # Sin backoff no se invoca sleep, aseguramos que la lógica completó los intentos


def test_normalize_datetime_handles_invalid_string(service: NewsService) -> None:
    assert service._normalize_datetime("not-a-date") is None
    assert service._normalize_datetime(None) is None


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

    async def crypto(_limit: int) -> list[dict[str, Any]]:
        return [latest_entry]

    async def finance(_limit: int) -> list[dict[str, Any]]:
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
