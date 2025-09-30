"""JWT helpers centralised for access and refresh tokens."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

JWT_ALG = "HS256"
ACCESS_MIN = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

ACCESS_SECRET = os.environ.get(
    "ACCESS_TOKEN_SECRET", os.environ.get("SECRET_KEY", "change-me")
)
REFRESH_SECRET = os.environ.get(
    "REFRESH_TOKEN_SECRET", os.environ.get("SECRET_KEY", "change-me")
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(sub: str, extra: Optional[Dict[str, Any]] = None) -> str:
    now = _now()
    payload: Dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_MIN)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, ACCESS_SECRET, algorithm=JWT_ALG)


def create_refresh_token(sub: str, jti: Optional[str] = None) -> str:
    now = _now()
    payload: Dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_DAYS)).timestamp()),
    }
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, REFRESH_SECRET, algorithm=JWT_ALG)


def decode_access(token: str) -> Dict[str, Any]:
    return jwt.decode(token, ACCESS_SECRET, algorithms=[JWT_ALG])


def decode_refresh(token: str) -> Dict[str, Any]:
    return jwt.decode(token, REFRESH_SECRET, algorithms=[JWT_ALG])
