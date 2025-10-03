"""Service responsible for retrieving curated news articles."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientError, ClientTimeout, ContentTypeError

try:  # pragma: no cover - allow running from different entrypoints
    from backend.utils.cache import CacheClient
    from backend.utils.config import Config
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.utils.cache import CacheClient  # type: ignore[no-redef]
    from backend.utils.config import Config  # type: ignore[no-redef]


LOGGER = logging.getLogger(__name__)


class NewsService:
    """Retrieve and normalize news articles from different providers."""

    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = 0.75

    def __init__(
        self,
        *,
        cache_client: CacheClient | None = None,
        session_factory: Callable[..., aiohttp.ClientSession] = aiohttp.ClientSession,
    ) -> None:
        self.cache = cache_client or CacheClient("news-service", ttl=120)
        self._session_factory = session_factory
        self._timeout = ClientTimeout(total=10)

    async def get_crypto_headlines(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return crypto headlines prioritising CryptoPanic and falling back to NewsAPI."""

        return await self._get_articles(
            cache_namespace="crypto",
            limit=limit,
            primary_fetcher=(
                self._fetch_cryptopanic if Config.CRYPTOPANIC_API_KEY else None
            ),
            fallback_query="cryptocurrency OR bitcoin OR ethereum",
        )

    async def get_finance_headlines(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return finance headlines prioritising Finfeed and falling back to NewsAPI."""

        return await self._get_articles(
            cache_namespace="finance",
            limit=limit,
            primary_fetcher=self._fetch_finfeed if Config.FINFEED_API_KEY else None,
            fallback_query="stock market OR finance",
        )

    async def get_latest_news(self, limit: int = 20) -> list[dict[str, Any]]:
        """Aggregate the freshest crypto and finance headlines."""

        limited = max(1, min(limit, 100))
        tasks = [
            asyncio.create_task(self.get_crypto_headlines(limited)),
            asyncio.create_task(self.get_finance_headlines(limited)),
        ]

        aggregated: list[dict[str, Any]] = []
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, Exception):
                LOGGER.warning("NewsService: error agregando noticias: %s", result)
                continue
            aggregated.extend(result)

        unique_items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in aggregated:
            identifier = (item.get("url") or item.get("title") or "").strip().lower()
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            unique_items.append(item)

        unique_items.sort(key=self._sort_key, reverse=True)
        return unique_items[:limited]

    async def _get_articles(
        self,
        *,
        cache_namespace: str,
        limit: int,
        primary_fetcher: Callable[[aiohttp.ClientSession, int], Any] | None,
        fallback_query: str,
    ) -> list[dict[str, Any]]:
        limited = max(1, min(limit, 50))
        cache_key = f"{cache_namespace}:{limited}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        articles: list[dict[str, Any]] = []

        async with self._session_factory(timeout=self._timeout) as session:
            if primary_fetcher is not None:
                articles = await self._call_with_retries(
                    primary_fetcher, session, limited
                )

            if not articles and Config.NEWSAPI_API_KEY:
                articles = await self._call_with_retries(
                    self._fetch_newsapi,
                    session,
                    limited,
                    query=fallback_query,
                )

        normalized: list[dict[str, Any]] = []
        seen_identifiers: set[str] = set()
        for item in articles:
            pruned = self._prune_article(item)
            title = (pruned.get("title") or "").strip()
            published = pruned.get("published_at")
            if not title or title.lower() == "untitled":
                continue
            if not published:
                continue
            identifier = (pruned.get("url") or title).strip().lower()
            if identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)
            normalized.append(pruned)
            if len(normalized) >= limited:
                break

        await self.cache.set(cache_key, normalized)
        return normalized

    async def _call_with_retries(
        self,
        handler: Callable[..., Any],
        session: aiohttp.ClientSession,
        limit: int,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        backoff = self.RETRY_BACKOFF
        for attempt in range(1, self.RETRY_ATTEMPTS + 1):
            try:
                result = await handler(session, limit, **kwargs)
                if not isinstance(result, list):  # pragma: no cover - defensive
                    LOGGER.warning("%s returned a non-list payload", handler.__name__)
                    return []
                return result
            except (
                TimeoutError,
                ClientError,
                ContentTypeError,
                KeyError,
                ValueError,
                TypeError,
            ) as exc:
                LOGGER.warning(
                    "NewsService attempt %s failed using %s: %s",
                    attempt,
                    handler.__name__,
                    exc,
                )
            except Exception as exc:  # pragma: no cover - unexpected failures
                LOGGER.exception(
                    "Unexpected error calling %s: %s",
                    handler.__name__,
                    exc,
                )
                break
            await asyncio.sleep(backoff)
            backoff *= 2
        return []

    async def _fetch_cryptopanic(
        self, session: aiohttp.ClientSession, limit: int, **_: Any
    ) -> list[dict[str, Any]]:
        if not Config.CRYPTOPANIC_API_KEY:
            raise KeyError("CRYPTOPANIC_API_KEY is not configured")

        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": Config.CRYPTOPANIC_API_KEY,
            "kind": "news",
            "filter": "important",
            "public": "true",
            "currencies": "BTC,ETH",
            "limit": limit,
        }
        payload = await self._fetch_json(
            session,
            url,
            params=params,
            source_name="CryptoPanic",
        )

        results = payload.get("results") or []
        articles: list[dict[str, Any]] = []
        for item in results:
            url_value = item.get("url") or item.get("source_url")
            source_info = item.get("source") or {}
            source_name = (
                source_info.get("title")
                or source_info.get("name")
                or source_info.get("domain")
                or self._extract_domain(url_value)
            )

            articles.append(
                {
                    "source": source_name or "CryptoPanic",
                    "title": item.get("title") or "Untitled",
                    "url": url_value,
                    "published_at": self._normalize_datetime(item.get("published_at")),
                    "summary": self._clean_html(
                        item.get("body") or item.get("title") or ""
                    ),
                }
            )
        return articles

    async def _fetch_finfeed(
        self, session: aiohttp.ClientSession, limit: int, **_: Any
    ) -> list[dict[str, Any]]:
        if not Config.FINFEED_API_KEY:
            raise KeyError("FINFEED_API_KEY is not configured")

        url = "https://api.finfeed.com/v1/news"
        params = {"limit": limit}
        headers = {"X-API-KEY": Config.FINFEED_API_KEY}
        payload = await self._fetch_json(
            session,
            url,
            params=params,
            headers=headers,
            source_name="Finfeed",
        )

        data: Iterable[dict[str, Any]] = (
            payload.get("data")
            or payload.get("articles")
            or payload.get("results")
            or []
        )

        articles: list[dict[str, Any]] = []
        for item in data:
            link = item.get("url") or item.get("link")
            articles.append(
                {
                    "source": item.get("source") or "Finfeed",
                    "title": item.get("title") or item.get("headline") or "Untitled",
                    "url": link,
                    "published_at": self._normalize_datetime(
                        item.get("published_at") or item.get("published")
                    ),
                    "summary": self._clean_html(
                        item.get("summary")
                        or item.get("description")
                        or item.get("excerpt")
                        or ""
                    ),
                }
            )
        return articles

    async def _fetch_newsapi(
        self,
        session: aiohttp.ClientSession,
        limit: int,
        *,
        query: str,
    ) -> list[dict[str, Any]]:
        if not Config.NEWSAPI_API_KEY:
            raise KeyError("NEWSAPI_API_KEY is not configured")

        url = "https://newsapi.org/v2/everything"
        headers = {"Authorization": f"Bearer {Config.NEWSAPI_API_KEY}"}
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": limit,
        }
        payload = await self._fetch_json(
            session,
            url,
            params=params,
            headers=headers,
            source_name="NewsAPI",
        )

        articles: list[dict[str, Any]] = []
        for article in payload.get("articles", []):
            source_info = article.get("source") or {}
            url_value = article.get("url")
            articles.append(
                {
                    "source": (
                        source_info.get("name")
                        or self._extract_domain(url_value)
                        or "NewsAPI"
                    ),
                    "title": article.get("title")
                    or article.get("description")
                    or "Untitled",
                    "url": url_value,
                    "published_at": self._normalize_datetime(
                        article.get("publishedAt")
                    ),
                    "summary": self._clean_html(
                        article.get("description") or article.get("content") or ""
                    ),
                }
            )
        return articles

    async def _fetch_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        source_name: str,
    ) -> dict[str, Any]:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status >= 400:
                raise ClientError(f"{source_name} returned status {response.status}")
            return await response.json()

    def _prune_article(self, article: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": article.get("source") or "Unknown",
            "title": article.get("title") or "Untitled",
            "url": article.get("url"),
            "published_at": article.get("published_at"),
            "summary": article.get("summary") or "",
        }

    def _sort_key(self, article: dict[str, Any]) -> datetime:
        published = article.get("published_at")
        if not published:
            return datetime.min.replace(tzinfo=UTC)
        try:
            return datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            try:
                return parsedate_to_datetime(published)
            except (TypeError, ValueError, IndexError):
                return datetime.min.replace(tzinfo=UTC)

    def _normalize_datetime(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError, IndexError):
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()

    def _clean_html(self, text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", text or "")
        return html.unescape(cleaned).strip()

    def _extract_domain(self, url: str | None) -> str:
        if not url:
            return "Unknown"
        try:
            return urlparse(url).netloc or "Unknown"
        except ValueError:
            return "Unknown"


news_service = NewsService()

__all__ = ["NewsService", "news_service"]
