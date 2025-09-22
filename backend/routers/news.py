"""News-related API routes."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

try:  # pragma: no cover - allow running from different entrypoints
    from services.market_service import market_service
except ImportError:  # pragma: no cover - fallback for package-based imports
    from backend.services.market_service import market_service  # type: ignore

router = APIRouter(prefix="/news", tags=["News"])


async def _get_news(category: str, limit: int) -> List[Dict[str, Any]]:
    try:
        articles = await market_service.get_news(category, limit=limit)
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

    articles = await _get_news("crypto", limit)
    return {"category": "crypto", "articles": articles}


@router.get("/finance")
async def get_finance_news(limit: int = 10) -> Dict[str, Any]:
    """Return finance news articles following the configured fallbacks."""

    articles = await _get_news("finance", limit)
    return {"category": "finance", "articles": articles}
