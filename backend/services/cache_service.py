"""Cache service abstraction supporting Redis and in-memory storage."""

# isort: skip_file  # 🧩 Codex fix
# ruff: noqa: I001  # 🧩 Codex fix
import hashlib  # 🧩 Codex fix
import json  # 🧩 Codex fix
import os
import time
from typing import Any

# ✅ Codex fix: soporte opcional para redis
try:  # pragma: no cover - redis puede no estar instalado en los tests
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

from backend.metrics.ai_metrics import (  # 🧩 Codex fix
    ai_cache_hit_total as _prom_cache_hit_total,
    ai_cache_miss_total as _prom_cache_miss_total,
)


class _ValueProxy:  # 🧩 Codex fix
    def __init__(self) -> None:
        self._current = 0.0

    def get(self) -> float:
        return self._current

    def increment(self, amount: float) -> None:
        self._current += amount


class _CounterProxy:  # 🧩 Codex fix
    def __init__(self, counter, **labels) -> None:
        self._counter = counter
        self._labels = labels
        self._value = _ValueProxy()

    def inc(self, amount: float = 1.0) -> None:
        if self._labels:
            self._counter.labels(**self._labels).inc(amount)
        else:
            self._counter.inc(amount)
        self._value.increment(amount)


ai_cache_hits_total = _CounterProxy(
    _prom_cache_hit_total, model="cache"
)  # 🧩 Codex fix
ai_cache_misses_total = _CounterProxy(
    _prom_cache_miss_total, model="cache"
)  # 🧩 Codex fix


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


class AICacheService:
    """High-level cache helper used by AIService."""

    def __init__(self, backend: CacheService | None = None) -> None:
        self._cache = backend or cache

    @staticmethod
    def _compose_key(route: str, prompt: str) -> str:
        # 🧩 Codex fix: claves determinísticas por ruta + hash del prompt
        digest = hashlib.sha256(prompt.encode()).hexdigest() if prompt else ""
        return f"ai:{route}:{digest}"

    async def get(self, route: str, prompt: str):
        key = self._compose_key(route, prompt)
        payload = self._cache.get(key)
        if payload is None:
            ai_cache_misses_total.inc()
            return None
        ai_cache_hits_total.inc()
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        return payload

    async def set(self, route: str, prompt: str, response, ttl: int) -> None:
        key = self._compose_key(route, prompt)
        if isinstance(response, dict | list):
            payload = json.dumps(response)
        else:
            payload = response
        self._cache.set(key, payload, ex=ttl)
