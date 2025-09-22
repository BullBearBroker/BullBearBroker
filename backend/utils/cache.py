import asyncio
import json
import time
from typing import Any, Dict, Optional, Tuple

from utils.config import Config

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:  # pragma: no cover - redis is optional
    redis = None


class CacheClient:
    """Pequeño cliente de caché con soporte opcional para Redis."""

    def __init__(self, namespace: str, ttl: int = 30):
        self.namespace = namespace
        self.ttl = ttl
        self._memory_cache: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()
        self._redis = self._init_redis()

    def _init_redis(self):
        if not Config.REDIS_URL or not redis:
            return None
        try:
            return redis.from_url(
                Config.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as exc:  # pragma: no cover - solo para logging
            print(f"CacheClient: Redis no disponible ({exc})")
            return None

    def _format_key(self, key: str) -> str:
        return f"{self.namespace}:{key}".lower()

    async def get(self, key: str) -> Optional[Any]:
        namespaced_key = self._format_key(key)
        if self._redis:
            try:
                data = await self._redis.get(namespaced_key)
            except Exception as exc:  # pragma: no cover - depende de redis
                print(f"CacheClient: error obteniendo valor de Redis ({exc})")
                return None
            if data is None:
                return None
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data

        async with self._lock:
            cached = self._memory_cache.get(namespaced_key)
            if not cached:
                return None
            expires_at, value = cached
            if expires_at < time.monotonic():
                del self._memory_cache[namespaced_key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or self.ttl
        namespaced_key = self._format_key(key)

        if self._redis:
            try:
                await self._redis.set(namespaced_key, json.dumps(value), ex=ttl)
                return
            except Exception as exc:  # pragma: no cover - depende de redis
                print(f"CacheClient: error guardando en Redis ({exc})")

        async with self._lock:
            expires_at = time.monotonic() + ttl
            self._memory_cache[namespaced_key] = (expires_at, value)


__all__ = ["CacheClient"]
