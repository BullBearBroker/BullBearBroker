from fastapi import APIRouter

from backend.services.ai_service import ai_service

router = APIRouter()


@router.post("/context")
async def ai_with_context(payload: dict):
    session_id = payload.get("session_id", "default")
    message = payload["message"]
    result = await ai_service.process_with_context(session_id, message)
    return result
