"""Streaming responses for AI endpoints."""

from __future__ import annotations

from contextlib import suppress
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

try:  # pragma: no cover - allow running from different entrypoints
    from backend.services.ai_service import ai_service
except ImportError:  # pragma: no cover
    from services.ai_service import ai_service  # type: ignore

router = APIRouter(tags=["AI"])


@router.post("/stream")
async def stream_message(request: Request, payload: dict) -> StreamingResponse:
    """Stream AI generated responses using Server-Sent Events."""

    message = payload.get("message", "") if isinstance(payload, dict) else ""

    async def stream_generator() -> AsyncGenerator[str, None]:
        stream = ai_service.stream_generate(message)
        try:
            async for chunk in stream:
                yield f"data: {chunk}\n\n"
                if await request.is_disconnected():
                    break
        finally:
            with suppress(Exception):
                await stream.aclose()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
