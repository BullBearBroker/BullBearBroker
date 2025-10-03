"""JWT helpers centralised for access and refresh tokens."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

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
    return datetime.now(UTC)


def create_access_token(sub: str, extra: dict[str, Any] | None = None) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_MIN)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, ACCESS_SECRET, algorithm=JWT_ALG)


def create_refresh_token(sub: str, jti: str | None = None) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_DAYS)).timestamp()),
    }
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, REFRESH_SECRET, algorithm=JWT_ALG)


def decode_access(token: str) -> dict[str, Any]:
    return jwt.decode(token, ACCESS_SECRET, algorithms=[JWT_ALG])


def decode_refresh(token: str) -> dict[str, Any]:
    return jwt.decode(token, REFRESH_SECRET, algorithms=[JWT_ALG])
