"""AI chat endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List  # [Codex] cambiado

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:  # pragma: no cover - allow running from different entrypoints
    from backend.services.ai_service import ai_service
except ImportError:  # pragma: no cover
    from services.ai_service import ai_service  # type: ignore

from backend.utils.config import Config


LOGGER = logging.getLogger(__name__)
router = APIRouter(tags=["AI"])


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Mensaje del usuario")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Contexto adicional opcional"
    )


class ChatResponse(BaseModel):
    response: str
    provider: Optional[str] = None
    used_data: bool = False  # [Codex] nuevo - informa si se usaron datos reales
    sources: List[str] = Field(default_factory=list)  # [Codex] nuevo - fuentes de datos


def _ensure_provider_available() -> None:
    if not (Config.MISTRAL_API_KEY or Config.HUGGINGFACE_API_KEY):
        LOGGER.error("No AI providers configured. Check MISTRAL_API_KEY or HUGGINGFACE_API_KEY")
        raise HTTPException(
            status_code=500,
            detail="No hay proveedores de IA configurados en el servidor.",
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """Procesa una consulta mediante los proveedores de IA configurados."""

    _ensure_provider_available()

    try:
        reply = await ai_service.process_message(payload.prompt, payload.context)
    except Exception as exc:  # pragma: no cover - errores inesperados
        LOGGER.exception("AIService failed to process prompt")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not reply:
        raise HTTPException(
            status_code=502, detail="El servicio de IA no devolvió ninguna respuesta"
        )

    # [Codex] cambiado - la respuesta ahora transporta metadatos del middleware
    text = getattr(reply, "text", str(reply))
    provider = getattr(reply, "provider", None) or "auto"
    used_data = bool(getattr(reply, "used_data", False))
    sources = list(getattr(reply, "sources", []) or [])

    return ChatResponse(
        response=text,
        provider=provider,
        used_data=used_data,
        sources=sources,
    )
