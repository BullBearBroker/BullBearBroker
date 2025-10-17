from __future__ import annotations

import os

import pytest

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.utils import cache as cache_module
from backend.utils.cache import CacheClient


@pytest.fixture(autouse=True)
def _disable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module.Config, "REDIS_URL", "")


@pytest.mark.asyncio
async def test_store_non_serializable_object_in_memory_cache() -> None:
    class CustomObject:
        def __init__(self) -> None:
            self.value = 42

        def method(self) -> int:
            return self.value

    cache = CacheClient("resilience", ttl=1)
    obj = CustomObject()
    await cache.set("complex", obj)
    retrieved = await cache.get("complex")
    assert retrieved is obj


@pytest.mark.asyncio
async def test_set_and_delete_clears_value() -> None:
    cache = CacheClient("resilience", ttl=5)
    await cache.set("temporary", {"value": 1})
    await cache.delete("temporary")
    assert await cache.get("temporary") is None


@pytest.mark.asyncio
async def test_expired_ttl_returns_none() -> None:
    cache = CacheClient("resilience", ttl=0)
    await cache.set("expired", "value", ttl=0)
    assert await cache.get("expired") is None


@pytest.mark.asyncio
async def test_extreme_keys_are_supported() -> None:
    cache = CacheClient("resilience", ttl=5)
    long_key = "x" * 256
    weird_key = "símbolo-Δ-测试"

    await cache.set(long_key, "long")
    await cache.set(weird_key, "unicode")

    assert await cache.get(long_key) == "long"
    assert await cache.get(weird_key) == "unicode"
