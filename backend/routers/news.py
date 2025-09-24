"""News-related API routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List

from fastapi import APIRouter, HTTPException

try:  # pragma: no cover - allow running from different entrypoints
    from services.news_service import news_service
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.services.news_service import news_service  # type: ignore

router = APIRouter(tags=["News"])


NewsFetcher = Callable[[int], Awaitable[List[Dict[str, Any]]]]


async def _get_news(
    category: str,
    limit: int,
    fetcher: NewsFetcher,
) -> List[Dict[str, Any]]:
    try:
        articles = await fetcher(limit)
    except Exception as exc:  # pragma: no cover - defensive logging happens in the service
        raise HTTPException(
            status_code=502,
            detail=f"Error obteniendo noticias de {category}: {exc}",
        ) from exc

    if not articles:
        raise HTTPException(
            status_code=404,
            detail=f"No hay noticias disponibles para {category}",
        )

    return articles


@router.get("/crypto")
async def get_crypto_news(limit: int = 10) -> Dict[str, Any]:
    """Return crypto-related news articles following the configured fallbacks."""

    articles = await _get_news("crypto", limit, news_service.get_crypto_headlines)
    return {"category": "crypto", "articles": articles}


@router.get("/finance")
async def get_finance_news(limit: int = 10) -> Dict[str, Any]:
    """Return finance news articles following the configured fallbacks."""

    articles = await _get_news("finance", limit, news_service.get_finance_headlines)
    return {"category": "finance", "articles": articles}
