from types import SimpleNamespace

import pytest

from backend.utils import cache as cache_module
from backend.utils.cache import CacheClient


@pytest.fixture(autouse=True)
def disable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module.Config, "REDIS_URL", None, raising=False)


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover
    return "asyncio"


@pytest.mark.anyio
async def test_missing_key_returns_none() -> None:
    client = CacheClient("resilience")
    assert await client.get("absent") is None


@pytest.mark.anyio
async def test_custom_ttl_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CacheClient("ttl", ttl=100)
    current = {"value": 10.0}

    monkeypatch.setattr(cache_module.time, "monotonic", lambda: current["value"])

    await client.set("key", "value", ttl=5)
    assert await client.get("key") == "value"

    current["value"] += 6
    assert await client.get("key") is None


@pytest.mark.anyio
async def test_delete_removes_active_key() -> None:
    client = CacheClient("delete")
    await client.set("key", "value")
    await client.delete("key")
    assert await client.get("key") is None


@pytest.mark.anyio
async def test_set_accepts_unexpected_types() -> None:
    client = CacheClient("types")
    payload = SimpleNamespace(symbol="AAPL", price=180.5)
    await client.set("snapshot", payload)
    assert await client.get("snapshot") == payload
