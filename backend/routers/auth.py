from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from models import User
from services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    user_service,
)
from utils.config import Config

router = APIRouter()
security = HTTPBearer()

# Secret key para JWT - obtenido desde configuración centralizada
SECRET_KEY = Config.JWT_SECRET_KEY
ALGORITHM = Config.JWT_ALGORITHM


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


def create_jwt_token(user: User) -> str:
    """Crear token JWT para el usuario"""
    payload = {
        "sub": user.email,
        "username": user.username,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def serialize_user(user: User) -> Dict[str, object]:
    """Serializar la información básica del usuario."""
    return {
        "email": user.email,
        "username": user.username,
        "subscription_level": user.subscription_level,
        "api_calls_today": user.api_calls_today,
    }


@router.post("/register")
async def register(request: RegisterRequest):
    """Endpoint para registrar nuevo usuario"""
    try:
        new_user = await user_service.create_user(
            email=request.email,
            username=request.username,
            password=request.password,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_jwt_token(new_user)

    return {
        "message": "Usuario registrado exitosamente",
        "token": token,
        "user": serialize_user(new_user),
    }


@router.post("/login")
async def login(request: LoginRequest):
    """Endpoint para login de usuario"""
    try:
        user = await user_service.authenticate_user(email=request.email, password=request.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    token = create_jwt_token(user)

    return {
        "message": "Login exitoso",
        "token": token,
        "user": serialize_user(user),
    }


@router.get("/users/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    """Obtener información del usuario actual"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]

        user = await user_service.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return serialize_user(user)

    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc
