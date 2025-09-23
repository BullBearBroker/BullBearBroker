from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

from backend.utils.config import Config

router = APIRouter(prefix="/ai", tags=["AI"])


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    reply: str


@router.post("/message", response_model=MessageResponse)
async def ai_message(request: MessageRequest):
    """
    Endpoint de IA usando Hugging Face Inference API.
    Responde de manera conversacional al mensaje del usuario.
    """

    token = Config.HUGGINGFACE_API_TOKEN
    model = Config.HUGGINGFACE_MODEL
    api_url = f"{Config.HUGGINGFACE_API_URL}/{model}"

    if not token:
        raise HTTPException(status_code=500, detail="Falta configurar HUGGINGFACE_API_TOKEN en el .env")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json={"inputs": request.message},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error en Hugging Face: {response.text}")

        data = response.json()

        # Respuesta según formato Hugging Face
        if isinstance(data, list) and "generated_text" in data[0]:
            reply = data[0]["generated_text"]
        elif isinstance(data, dict) and "generated_text" in data:
            reply = data["generated_text"]
        else:
            reply = str(data)

        return MessageResponse(reply=reply.strip())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error llamando a Hugging Face: {e}")
