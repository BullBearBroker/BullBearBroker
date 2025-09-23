from __future__ import annotations

from datetime import timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from backend.models import User
from backend.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    user_service,
)

router = APIRouter()
security = HTTPBearer()


# -------------------------
# Pydantic Schemas
# -------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


def serialize_user(user: User) -> Dict[str, object]:
    """Serializar la información básica del usuario."""
    return {
        "id": str(user.id),
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# -------------------------
# Endpoints
# -------------------------
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Endpoint para registrar nuevo usuario"""
    try:
        if len(user_data.password) < 6:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

        try:
            new_user = user_service.create_user(
                email=user_data.email,
                password=user_data.password,
            )
        except UserAlreadyExistsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        created_at = new_user.created_at.isoformat() if new_user.created_at else None

        return {
            "id": str(new_user.id),
            "email": new_user.email,
            "created_at": created_at,
        }

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Campo faltante: {str(e)}")


@router.post("/login")
async def login(credentials: UserLogin):
    """Endpoint para login de usuario"""
    try:
        try:
            user = user_service.authenticate_user(
                email=credentials.email,
                password=credentials.password,
            )
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        token, session = user_service.create_session(
            user_id=user.id,
            expires_in=timedelta(hours=24),
        )

        return {
            "message": "Login exitoso",
            "token": token,
            "user": serialize_user(user),
            "expires_at": session.expires_at.isoformat(),
        }

    except KeyError:
        raise HTTPException(status_code=400, detail="Email y password requeridos")


@router.get("/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    """Obtener información del usuario actual"""
    try:
        user = user_service.get_current_user(token.credentials)
        user_service.register_session_activity(token.credentials)
        return serialize_user(user)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
