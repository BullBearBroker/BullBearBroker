from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat/message")
async def chat_message(request: ChatRequest):
    return {
        "success": True,
        "response": f"Respuesta a: {request.message}",
        "test": "funcionando",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
