from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from backend.utils.cache import CacheClient

BACKOFF_WINDOWS: list[float] = [60.0, 120.0, 300.0, 900.0]
_CACHE_TTL = int(max(BACKOFF_WINDOWS[-1] * 2, 1800))


@dataclass
class LoginBackoffState:
    failures: int = 0
    locked_until: Optional[float] = None

    @property
    def remaining(self) -> float:
        if self.locked_until is None:
            return 0.0
        delta = self.locked_until - time.time()
        return max(0.0, delta)


class LoginBackoffManager:
    def __init__(self, cache: CacheClient):
        self._cache = cache

    async def _load(self, email_hash: str) -> LoginBackoffState:
        payload = await self._cache.get(email_hash)
        if not payload:
            return LoginBackoffState()
        return LoginBackoffState(
            failures=int(payload.get("failures", 0)),
            locked_until=float(payload.get("locked_until"))
            if payload.get("locked_until") is not None
            else None,
        )

    async def _save(self, email_hash: str, state: LoginBackoffState) -> None:
        await self._cache.set(
            email_hash,
            {"failures": state.failures, "locked_until": state.locked_until},
            ttl=_CACHE_TTL,
        )

    async def register_failure(self, email_hash: str, *, start_after: int = 1) -> float:
        state = await self._load(email_hash)
        state.failures += 1
        effective_start = max(1, start_after)
        seconds = 0.0
        if state.failures >= effective_start:
            window_index = min(
                state.failures - effective_start,
                len(BACKOFF_WINDOWS) - 1,
            )
            seconds = BACKOFF_WINDOWS[window_index]
            state.locked_until = time.time() + seconds
        else:
            state.locked_until = None
        await self._save(email_hash, state)
        return seconds

    async def clear(self, email_hash: str) -> None:
        await self._cache.delete(email_hash)

    async def clear_all(self) -> None:
        await self._cache.clear_namespace()

    async def remaining_seconds(self, email_hash: str) -> float:
        state = await self._load(email_hash)
        remaining = state.remaining
        if remaining <= 0 and state.failures > 0 and state.locked_until is not None:
            state.locked_until = None
            await self._save(email_hash, state)
        return remaining

    async def failure_count(self, email_hash: str) -> int:
        state = await self._load(email_hash)
        return state.failures

    async def required_wait_seconds(self, email_hash: str) -> int:
        remaining = await self.remaining_seconds(email_hash)
        if remaining <= 0:
            return 0
        return max(1, math.ceil(remaining))


login_backoff = LoginBackoffManager(CacheClient("login-backoff", ttl=_CACHE_TTL))

__all__ = [
    "BACKOFF_WINDOWS",
    "LoginBackoffManager",
    "login_backoff",
]
