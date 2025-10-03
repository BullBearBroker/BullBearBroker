"""AI chat endpoints with persistent history."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    ChatMessage as ChatMessageModel,
    ChatSession as ChatSessionModel,
    User,
)
from backend.utils.config import Config

try:  # pragma: no cover - allow running from different entrypoints
    from backend.services.ai_service import AIResponsePayload, ai_service
except ImportError:  # pragma: no cover
    from services.ai_service import AIResponsePayload, ai_service  # type: ignore

try:  # pragma: no cover - optional when running without user_service
    from backend.services.user_service import InvalidTokenError, user_service
except Exception:  # pragma: no cover
    user_service = None  # type: ignore[assignment]
    InvalidTokenError = Exception  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)
router = APIRouter(tags=["AI"])
security = HTTPBearer()


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Mensaje del usuario")
    context: dict[str, Any] | None = Field(
        default=None, description="Contexto adicional opcional"
    )
    session_id: UUID | None = Field(
        default=None,
        description="Identificador de la sesión persistida",
    )


class ChatResponse(BaseModel):
    response: str
    provider: str | None = None
    used_data: bool = False
    sources: list[str] = Field(default_factory=list)
    session_id: UUID


class PersistedMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    created_at: datetime
    messages: list[PersistedMessage]


def _ensure_provider_available() -> None:
    if not (Config.MISTRAL_API_KEY or Config.HUGGINGFACE_API_KEY):
        LOGGER.error(
            "No AI providers configured. Check MISTRAL_API_KEY or HUGGINGFACE_API_KEY"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hay proveedores de IA configurados en el servidor.",
        )


def _ensure_user_service_available() -> None:
    if user_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de usuarios no disponible",
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    _ensure_user_service_available()

    try:
        return await asyncio.to_thread(
            user_service.get_current_user, credentials.credentials
        )
    except InvalidTokenError as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


def _fetch_session(
    db: Session, user_id: UUID, session_id: UUID | None
) -> ChatSessionModel:
    if session_id is None:
        session = ChatSessionModel(user_id=user_id)
        db.add(session)
        db.flush()
        return session

    session = (
        db.query(ChatSessionModel)
        .filter(ChatSessionModel.id == session_id, ChatSessionModel.user_id == user_id)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada"
        )
    return session


def _load_history(db: Session, session: ChatSessionModel) -> list[ChatMessageModel]:
    return (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.session_id == session.id)
        .order_by(ChatMessageModel.created_at.asc())
        .all()
    )


def _prepare_context(
    base_context: dict[str, Any] | None,
    history: list[ChatMessageModel],
) -> dict[str, Any]:
    context: dict[str, Any] = dict(base_context or {})
    serialized_history = [
        {"role": message.role, "content": message.content}
        for message in history
        if message.content
    ]
    if serialized_history:
        existing_history = list(context.get("history") or [])
        context["history"] = serialized_history + existing_history
    return context


def _persist_message(
    db: Session,
    session: ChatSessionModel,
    role: str,
    content: str,
) -> ChatMessageModel:
    message = ChatMessageModel(session_id=session.id, role=role, content=content)
    db.add(message)
    return message


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    """Procesa una consulta mediante los proveedores de IA configurados y la persiste."""

    _ensure_provider_available()

    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mensaje no puede estar vacío",
        )

    session = _fetch_session(db, current_user.id, payload.session_id)
    history = _load_history(db, session)
    context = _prepare_context(payload.context, history)

    user_message = _persist_message(db, session, "user", prompt)

    try:
        reply: AIResponsePayload = await ai_service.process_message(prompt, context)
    except Exception as exc:  # pragma: no cover - errores inesperados
        LOGGER.exception("AIService failed to process prompt")
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not reply:
        db.rollback()
        raise HTTPException(
            status_code=502, detail="El servicio de IA no devolvió ninguna respuesta"
        )

    text = getattr(reply, "text", str(reply))
    provider = getattr(reply, "provider", None) or "auto"
    used_data = bool(getattr(reply, "used_data", False))
    sources = list(getattr(reply, "sources", []) or [])

    assistant_message = _persist_message(db, session, "assistant", text)

    try:
        db.commit()
    except Exception as exc:  # pragma: no cover - unexpected db error
        LOGGER.exception("Failed to persist chat messages")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="No se pudo guardar la conversación"
        ) from exc

    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(session)

    return ChatResponse(
        response=text,
        provider=provider,
        used_data=used_data,
        sources=sources,
        session_id=session.id,
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_history(
    session_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatHistoryResponse:
    _ensure_user_service_available()

    session = (
        db.query(ChatSessionModel)
        .filter(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == current_user.id,
        )
        .one_or_none()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada"
        )

    messages = _load_history(db, session)

    return ChatHistoryResponse(
        session_id=session.id,
        created_at=session.created_at,
        messages=[PersistedMessage.model_validate(message) for message in messages],
    )
