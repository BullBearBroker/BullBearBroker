import pytest

from backend.utils import cache as cache_module
from backend.utils.cache import CacheClient


@pytest.fixture(autouse=True)
def disable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module.Config, "REDIS_URL", None, raising=False)


@pytest.mark.asyncio
async def test_set_get_delete_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CacheClient("test-namespace", ttl=10)
    await client.set("key", {"value": 1})
    assert await client.get("key") == {"value": 1}

    await client.delete("key")
    assert await client.get("key") is None


@pytest.mark.asyncio
async def test_missing_key_returns_none() -> None:
    client = CacheClient("missing")
    assert await client.get("absent") is None


@pytest.mark.asyncio
async def test_ttl_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CacheClient("ttl", ttl=5)
    fake_time = {"value": 100.0}

    monkeypatch.setattr(cache_module.time, "monotonic", lambda: fake_time["value"])

    await client.set("key", "value")
    assert await client.get("key") == "value"

    fake_time["value"] += 6
    assert await client.get("key") is None


@pytest.mark.asyncio
async def test_large_values_supported() -> None:
    client = CacheClient("large")
    large_value = "x" * (1024 * 1024)
    await client.set("blob", large_value)
    assert await client.get("blob") == large_value
