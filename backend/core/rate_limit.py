"""Shared helpers for rate limit dependencies with graceful fallbacks."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict

from fastapi import HTTPException, Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

_IN_MEMORY_BUCKETS: Dict[str, list[float]] = defaultdict(list)


def rate_limit(
    *,
    times: int,
    seconds: int,
    identifier: str,
    detail: str = "Too Many Requests",
    fallback_times: int | None = None,
) -> Callable[[Request, Response], Awaitable[None]]:
    """Return a dependency that enforces rate limits with Redis or an in-memory fallback."""

    limiter = RateLimiter(times=times, seconds=seconds)
    bucket_prefix = f"{identifier}:{times}:{seconds}"
    fallback_limit = fallback_times or times

    async def _dependency(request: Request, response: Response) -> None:
        redis_client = getattr(FastAPILimiter, "redis", None)
        if redis_client is not None:
            try:
                await limiter(request, response)
                return
            except Exception:
                # Redis sin inicializar; cae al modo en memoria
                pass

        client_host = request.client.host if request.client else "unknown"
        bucket_key = f"{client_host}:{bucket_prefix}"
        window = _IN_MEMORY_BUCKETS[bucket_key]
        now = time.monotonic()
        window[:] = [tick for tick in window if now - tick < seconds]
        if len(window) >= fallback_limit:
            raise HTTPException(status_code=429, detail=detail)
        window.append(now)

    return _dependency


def reset_rate_limiter_cache(identifier: str | None = None) -> None:
    """Utility used in tests to reset the fallback buckets."""

    if identifier is None:
        _IN_MEMORY_BUCKETS.clear()
        return

    keys = [key for key in _IN_MEMORY_BUCKETS if key.startswith(identifier)]
    for key in keys:
        _IN_MEMORY_BUCKETS.pop(key, None)


__all__ = ["rate_limit", "reset_rate_limiter_cache"]
