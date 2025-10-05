"""Notification testing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from backend.services.notification_dispatcher import notification_dispatcher


router = APIRouter()


@router.post("/broadcast", status_code=status.HTTP_202_ACCEPTED)
async def broadcast_test(request: Request) -> dict[str, object]:
    payload = await request.json()
    await notification_dispatcher.broadcast_event("manual", payload)
    return {"status": "ok", "sent": len(str(payload))}


__all__ = ["router"]
