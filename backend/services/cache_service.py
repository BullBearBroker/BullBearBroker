"""Cache service abstraction supporting Redis and in-memory storage."""

# ✅ Codex fix: soporte opcional para redis
try:  # pragma: no cover - redis puede no estar instalado en los tests
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

import asyncio
import hashlib
import json
import os
import time
from typing import Any

from backend.utils.config import get_redis
from prometheus_client import Counter


class CacheService:  # ✅ Codex fix: servicio dual Redis/memoria
    def __init__(self) -> None:
        url = os.getenv("REDIS_URL", None)
        if url and redis is not None:
            self.client = redis.from_url(url, decode_responses=True)
            self.backend = "redis"
        else:
            self.client: dict[str, dict[str, Any]] = {}
            self.backend = "memory"

    def get(self, key: str):  # ✅ Codex fix: lectura con expiración
        if self.backend == "redis":
            return self.client.get(key)
        entry = self.client.get(key)
        if not entry:
            return None
        expires_at = entry.get("expires_at")
        if expires_at and expires_at < time.time():
            self.client.pop(key, None)
            return None
        return entry.get("value")

    def set(
        self, key: str, value, ex: int | None = None
    ) -> None:  # ✅ Codex fix: escritura con TTL
        if self.backend == "redis":
            self.client.set(key, value, ex=ex)
        else:
            expires_at = time.time() + ex if ex else None
            self.client[key] = {"value": value, "expires_at": expires_at}


cache = CacheService()  # ✅ Codex fix: instancia compartida

ai_cache_hits_total = Counter(
    "ai_cache_hits_total", "Respuestas IA servidas desde cache"
)
ai_cache_misses_total = Counter(
    "ai_cache_misses_total", "Respuestas IA sin cache"
)


class AICacheService:
    def __init__(self):
        self.redis = get_redis()
        self._memory_cache: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    def _key(self, route: str, prompt: str):
        hashed = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return f"ai:{route}:{hashed}"

    async def get(self, route: str, prompt: str):
        key = self._key(route, prompt)
        data: str | None = None
        if self.redis is not None:
            try:
                data = await self.redis.get(key)
            except Exception:
                data = None
        if data is None:
            async with self._lock:
                payload = self._memory_cache.get(key)
                if payload:
                    cached_value, expires_at = payload
                    if expires_at is not None and expires_at < time.time():
                        self._memory_cache.pop(key, None)
                    else:
                        data = cached_value
        if data:
            ai_cache_hits_total.inc()
            return json.loads(data)
        ai_cache_misses_total.inc()
        return None

    async def set(self, route: str, prompt: str, response: dict, ttl: int):
        key = self._key(route, prompt)
        payload = json.dumps(response)
        if self.redis is not None:
            try:
                await self.redis.setex(key, ttl, payload)
                return
            except Exception:
                pass
        async with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._memory_cache[key] = (payload, expires_at)
