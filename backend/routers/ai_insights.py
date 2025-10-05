"""Router para insights generados por IA."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from backend.services.ai_service import AIService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/insights")
async def generate_insights(request: Request, payload: dict):
    """Genera insights automatizados sobre un símbolo financiero."""

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload inválido",
        )

    symbol = payload.get("symbol")
    timeframe = payload.get("timeframe", "1d")
    profile = payload.get("profile", "investor")

    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El campo 'symbol' es requerido",
        )

    ai = AIService()
    result = await ai.generate_insight(symbol=symbol, timeframe=timeframe, profile=profile)

    if isinstance(result, dict) and result.get("error"):
        logger.error(
            json.dumps(
                {
                    "ai_event": "insight_generation_failed",
                    "symbol": symbol,
                    "error": result["error"],
                }
            )
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id and isinstance(result, dict):
        result.setdefault("correlation_id", correlation_id)

    return result
