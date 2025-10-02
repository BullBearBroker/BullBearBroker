"""Shared helpers for rate limit dependencies with graceful fallbacks."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Optional

from fastapi import HTTPException, Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from backend.utils.config import Config

_IN_MEMORY_BUCKETS: Dict[str, list[float]] = defaultdict(list)

LimitCallback = Callable[[Request, str], None]


async def identifier_login_by_email(request: Request) -> str:
    """Return an identifier for login rate limiting keyed by email when available."""

    email = ""
    try:
        data = await request.json()
        email = str(data.get("email", "")).strip().lower()
    except Exception:  # pragma: no cover - body parsing failures fall back to IP
        pass

    if email:
        return f"login:{email}"

    host = request.client.host if request.client else "unknown"
    return f"login-ip:{host}"


def login_rate_limiter(
    times: int = 5,
    seconds: int = 60,
    *,
    detail: str = "Demasiados intentos de inicio de sesión. Intenta nuevamente más tarde.",
    on_limit: LimitCallback | None = None,
    state_attribute: str | None = None,
) -> Callable[[Request, Response], Awaitable[None]]:
    """Factory that enforces login rate limits keyed by email with graceful fallbacks."""

    limiter = RateLimiter(times=times, seconds=seconds, identifier=identifier_login_by_email)

    async def _dependency(request: Request, response: Response) -> None:
        identifier = await identifier_login_by_email(request)
        email_hash: Optional[str] = None
        if identifier.startswith("login:"):
            raw_email = identifier.split(":", 1)[1]
            email_hash = hashlib.sha256(raw_email.encode("utf-8")).hexdigest()[:8]
        setattr(request.state, "login_email_hash", email_hash)

        if state_attribute:
            setattr(request.state, state_attribute, False)

        redis_client = getattr(FastAPILimiter, "redis", None)
        if redis_client is not None:
            try:
                await limiter(request, response)
                return
            except HTTPException:
                if state_attribute:
                    setattr(request.state, state_attribute, True)
                if on_limit:
                    on_limit(request, "email")
                raise HTTPException(status_code=429, detail=detail)
            except Exception:
                pass

        bucket_key = f"{identifier}:{times}:{seconds}"
        window = _IN_MEMORY_BUCKETS[bucket_key]
        now = time.monotonic()
        window[:] = [tick for tick in window if now - tick < seconds]
        if len(window) >= times:
            if state_attribute:
                setattr(request.state, state_attribute, True)
            if on_limit:
                on_limit(request, "email")
            raise HTTPException(status_code=429, detail=detail)
        window.append(now)
        if state_attribute:
            setattr(request.state, state_attribute, False)

    return _dependency


def rate_limit(
    *,
    times: int,
    seconds: int,
    identifier: str,
    detail: str = "Too Many Requests",
    fallback_times: int | None = None,
    on_limit: LimitCallback | None = None,
    on_limit_dimension: str | None = None,
    state_attribute: str | None = None,
) -> Callable[[Request, Response], Awaitable[None]]:
    """Return a dependency that enforces rate limits with Redis or an in-memory fallback."""

    limiter = RateLimiter(times=times, seconds=seconds)
    bucket_prefix = f"{identifier}:{times}:{seconds}"
    fallback_limit = fallback_times or times

    async def _dependency(request: Request, response: Response) -> None:
        if state_attribute:
            setattr(request.state, state_attribute, False)

        if (
            Config.TESTING
            and request.url.path == "/api/auth/login"
            and identifier == "auth_login_ip"
        ):
            if state_attribute:
                setattr(request.state, state_attribute, False)
            return
        redis_client = getattr(FastAPILimiter, "redis", None)
        if redis_client is not None:
            try:
                await limiter(request, response)
                return
            except HTTPException:
                if state_attribute:
                    setattr(request.state, state_attribute, True)
                if on_limit:
                    dimension = on_limit_dimension or identifier
                    on_limit(request, dimension)
                raise HTTPException(status_code=429, detail=detail)
            except Exception:
                # Redis sin inicializar; cae al modo en memoria
                pass

        client_host = request.client.host if request.client else "unknown"
        bucket_key = f"{client_host}:{bucket_prefix}"
        window = _IN_MEMORY_BUCKETS[bucket_key]
        now = time.monotonic()
        window[:] = [tick for tick in window if now - tick < seconds]
        if len(window) >= fallback_limit:
            if state_attribute:
                setattr(request.state, state_attribute, True)
            if on_limit:
                dimension = on_limit_dimension or identifier
                on_limit(request, dimension)
            raise HTTPException(status_code=429, detail=detail)
        window.append(now)
        if state_attribute:
            setattr(request.state, state_attribute, False)

    return _dependency


def reset_rate_limiter_cache(identifier: str | None = None) -> None:
    """Utility used in tests to reset the fallback buckets."""

    if identifier is None:
        _IN_MEMORY_BUCKETS.clear()
        return

    keys = [
        key
        for key in list(_IN_MEMORY_BUCKETS.keys())
        if key.startswith(identifier) or f":{identifier}:" in key
    ]
    for key in keys:
        _IN_MEMORY_BUCKETS.pop(key, None)


async def clear_testing_state() -> None:
    """Reset Redis and in-memory rate limit buckets for tests."""

    redis_client = getattr(FastAPILimiter, "redis", None)
    if redis_client is not None:
        try:
            login_ip_pattern = "auth_login_ip*"
            keys = await redis_client.keys(login_ip_pattern)
            if keys:
                await redis_client.delete(*keys)
        except Exception:  # pragma: no cover - limpieza defensiva
            pass
        try:
            await redis_client.flushdb()
        except Exception:  # pragma: no cover - limpieza defensiva
            pass
    reset_rate_limiter_cache()


__all__ = [
    "identifier_login_by_email",
    "login_rate_limiter",
    "rate_limit",
    "reset_rate_limiter_cache",
    "clear_testing_state",
]
