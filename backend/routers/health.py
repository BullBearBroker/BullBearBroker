from fastapi import APIRouter
import os

router = APIRouter(prefix="", tags=["health"])

@router.get("/health")
def health():
    # Señal mínima para monitoreo
    return {
        "status": "ok",
        "env": os.getenv("ENV", "unknown"),
    }

@router.get("/version")
def version():
    # Si quieres, lee de un archivo VERSION o de git más adelante
    return {"version": "0.1.0"}
