from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Dict

from pydantic import BaseModel, EmailStr

from backend.core.security import create_access_token, create_refresh_token, decode_refresh
from backend.database import get_db
from backend.models import User
from backend.models.refresh_token import RefreshToken
from backend.schemas.auth import RefreshRequest, TokenPair
from backend.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    user_service,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    revoke_all: bool = False


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    try:
        new_user = user_service.create_user(
            email=user_data.email,
            password=user_data.password,
        )
    except UserAlreadyExistsError as exc:  # pragma: no cover - tests cubren el éxito
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
    }


@router.post("/login", response_model=TokenPair)
async def login(credentials: UserLogin, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = user_service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    sub = str(user.id)
    jti = str(uuid4())
    refresh_token = create_refresh_token(sub=sub, jti=jti)
    refresh_payload = decode_refresh(refresh_token)
    refresh_expires = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)

    # ⬇️ Persistimos el refresh token siempre con nuestro servicio
    user_service.store_refresh_token(user.id, refresh_token)

    access_token = create_access_token(sub=sub)
    access_expires = datetime.utcnow() + timedelta(minutes=15)
    user_service.register_external_session(user.id, access_token, access_expires)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires.isoformat(),
        refresh_expires_at=refresh_expires.isoformat(),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    token_str = req.refresh_token
    db_token = None
    if db is not None:
        db_token = db.query(RefreshToken).filter(RefreshToken.token == token_str).first()

    if db_token:
        try:
            payload = decode_refresh(token_str)
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
            sub_uuid = UUID(sub)
        except (jwt.PyJWTError, ValueError):
            db.delete(db_token)
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        db.delete(db_token)
        new_refresh = create_refresh_token(sub=sub, jti=str(uuid4()))
        db.add(RefreshToken(user_id=sub_uuid, token=new_refresh))
        db.commit()
        refresh_payload = decode_refresh(new_refresh)
        refresh_expires = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
        access_token = create_access_token(sub=sub)
        access_expires = datetime.utcnow() + timedelta(minutes=15)
        user_service.register_external_session(sub_uuid, access_token, access_expires)
        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh,
            access_expires_at=access_expires.isoformat(),
            refresh_expires_at=refresh_expires.isoformat(),
        )

    try:
        user, new_refresh, refresh_expires = user_service.rotate_refresh_token(token_str)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token = create_access_token(sub=str(user.id))
    access_expires = datetime.utcnow() + timedelta(minutes=15)
    user_service.register_external_session(user.id, access_token, access_expires)
    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh,
        access_expires_at=access_expires.isoformat(),
        refresh_expires_at=refresh_expires.isoformat(),
    )


@router.post("/logout")
def logout(req: LogoutRequest, db: Session = Depends(get_db)) -> Dict[str, str]:
    if req.revoke_all:
        if not req.refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token required")
        try:
            payload = decode_refresh(req.refresh_token)
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=400, detail="refresh_token invalid")
            sub_uuid = UUID(sub)
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(status_code=400, detail="refresh_token invalid")

        if db is not None:
            db.query(RefreshToken).filter(RefreshToken.user_id == sub_uuid).delete()
            db.commit()
        else:
            user_service.revoke_all_refresh_tokens(sub_uuid)
        return {"detail": "All sessions revoked"}

    if not req.refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token required")

    if db is not None:
        db.query(RefreshToken).filter(RefreshToken.token == req.refresh_token).delete()
        db.commit()
    else:
        user_service.revoke_refresh_token(req.refresh_token)

    return {"detail": "Session revoked"}


@router.get("/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    try:
        user = user_service.get_current_user(token.credentials)
        user_service.register_session_activity(token.credentials)
        return {
            "id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
