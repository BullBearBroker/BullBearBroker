"""Shared helpers for rate limit dependencies with graceful fallbacks."""

from __future__ import annotations

import contextlib
import hashlib
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from backend.core.logging_config import get_logger, log_event
from backend.utils.config import Config

_IN_MEMORY_BUCKETS: dict[str, list[float]] = defaultdict(list)

LimitCallback = Callable[[Request, str], None]


LOGGER = get_logger(service="rate_limit")


class SimpleRateLimiter:
    """Minimal rate limiter compatible with the test helpers."""

    def __init__(self) -> None:
        self._limits: dict[str, tuple[int, int]] = {}

    def configure(self, key: str, *, times: int, seconds: int) -> None:
        """Persist configuration for a rate limit key."""

        times = max(1, int(times))
        seconds = max(1, int(seconds))
        self._limits[key] = (times, seconds)

    async def record_hit(
        self,
        *,
        key: str,
        client_ip: str,
        weight: int = 1,
        limit: int | None = None,
        window: int | None = None,
        detail: str = "Too Many Requests",
    ) -> None:
        """Record a hit for the given key, raising when the limit is exceeded."""

        configured = self._limits.get(key)
        max_requests, window_seconds = configured if configured else (
            limit or 5,
            window or 60,
        )

        max_requests = max(1, int(max_requests))
        window_seconds = max(1, int(window_seconds))
        step = max(1, int(weight))
        bucket_key = f"{client_ip}:{key}:{max_requests}:{window_seconds}"
        bucket = _IN_MEMORY_BUCKETS[bucket_key]
        now = time.monotonic()
        bucket[:] = [tick for tick in bucket if now - tick < window_seconds]

        if len(bucket) + step > max_requests:
            raise HTTPException(status_code=429, detail=detail)

        bucket.extend([now] * step)


# Default alert dispatch limit (5 requests per minute unless overridden)
_ALERT_DISPATCH_LIMIT_TIMES = max(
    1, int(getattr(Config, "ALERTS_DISPATCH_RATE_LIMIT_TIMES", 5))
)
_ALERT_DISPATCH_LIMIT_WINDOW = max(
    1, int(getattr(Config, "ALERTS_DISPATCH_RATE_LIMIT_WINDOW", 60))
)

rate_limiter = SimpleRateLimiter()
rate_limiter.configure(
    "alerts:dispatch",
    times=_ALERT_DISPATCH_LIMIT_TIMES,
    seconds=_ALERT_DISPATCH_LIMIT_WINDOW,
)


async def identifier_login_by_email(request: Request) -> str:
    """Return an identifier for login rate limiting keyed by email when available."""

    email = ""
    with contextlib.suppress(
        Exception
    ):  # pragma: no cover - body parsing failures fall back to IP
        data = await request.json()
        email = str(data.get("email", "")).strip().lower()

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

    limiter = RateLimiter(
        times=times, seconds=seconds, identifier=identifier_login_by_email
    )

    async def _dependency(request: Request, response: Response) -> None:
        identifier = await identifier_login_by_email(request)
        email_hash: str | None = None
        if identifier.startswith("login:"):
            raw_email = identifier.split(":", 1)[1]
            email_hash = hashlib.sha256(raw_email.encode("utf-8")).hexdigest()[:8]
        request.state.login_email_hash = email_hash

        if state_attribute:
            setattr(request.state, state_attribute, False)

        redis_client = getattr(FastAPILimiter, "redis", None)
        if redis_client is not None:
            try:
                await limiter(request, response)
                return
            except HTTPException as err:
                if state_attribute:
                    setattr(request.state, state_attribute, True)
                if on_limit:
                    on_limit(request, "email")
                raise HTTPException(status_code=429, detail=detail) from err
            except Exception as exc:
                payload = {
                    "service": "rate_limit",
                    "event": "dependency_unavailable",
                    "level": "warning",
                    "dependency": "redis",
                }
                if email_hash:
                    payload["email_hash"] = email_hash
                payload["error"] = str(exc)
                log_event(LOGGER, **payload)

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

        redis_client = getattr(FastAPILimiter, "redis", None)
        if redis_client is not None:
            try:
                await limiter(request, response)
                return
            except HTTPException as err:
                if state_attribute:
                    setattr(request.state, state_attribute, True)
                if on_limit:
                    dimension = on_limit_dimension or identifier
                    on_limit(request, dimension)
                raise HTTPException(status_code=429, detail=detail) from err
            except Exception as exc:
                log_event(
                    LOGGER,
                    service="rate_limit",
                    event="dependency_unavailable",
                    level="warning",
                    dependency="redis",
                    identifier=identifier,
                    error=str(exc),
                )

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
        with contextlib.suppress(Exception):  # pragma: no cover - limpieza defensiva
            login_ip_pattern = "auth_login_ip*"
            keys = await redis_client.keys(login_ip_pattern)
            if keys:
                await redis_client.delete(*keys)
        with contextlib.suppress(Exception):  # pragma: no cover - limpieza defensiva
            await redis_client.flushdb()
    reset_rate_limiter_cache()


__all__ = [
    "SimpleRateLimiter",
    "rate_limiter",
    "identifier_login_by_email",
    "login_rate_limiter",
    "rate_limit",
    "reset_rate_limiter_cache",
    "clear_testing_state",
]
