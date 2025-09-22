from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
async def register(user_data: dict):
    """Endpoint para registrar nuevo usuario"""
    try:
        if len(user_data["password"]) < 6:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

        try:
            new_user = user_service.create_user(
                email=user_data["email"],
                username=user_data["username"],
                password=user_data["password"],
            )
        except UserAlreadyExistsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        token = create_jwt_token(new_user)

        return {
            "message": "Usuario registrado exitosamente",
            "token": token,
            "user": serialize_user(new_user),
        }

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Campo faltante: {str(e)}")


@router.post("/login")
async def login(credentials: dict):
    """Endpoint para login de usuario"""
    try:
        email = credentials["email"]
        password = credentials["password"]

        try:
            user = user_service.authenticate_user(email=email, password=password)
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        token = create_jwt_token(user)
        user_service.create_session(user_id=user.id, token=token, expires_in=timedelta(hours=24))

        return {
            "message": "Login exitoso",
            "token": token,
            "user": serialize_user(user),
        }

    except KeyError:
        raise HTTPException(status_code=400, detail="Email y password requeridos")


@router.get("/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    """Obtener información del usuario actual"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]

        user = user_service.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user_service.register_session_activity(token.credentials)

        return serialize_user(user)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
