"""Cache service abstraction supporting Redis and in-memory storage."""

# ✅ Codex fix: soporte opcional para redis
try:  # pragma: no cover - redis puede no estar instalado en los tests
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

import os
import time
from typing import Any


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
