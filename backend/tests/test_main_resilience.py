from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.database import Base
from backend.main import app


class DummyRedis:
    def __init__(self) -> None:
        self.pings = 0
        self.closed = False

    async def ping(self) -> bool:
        self.pings += 1
        return True

    async def close(self) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_lifespan_records_startup_and_shutdown_logs(monkeypatch: pytest.MonkeyPatch, caplog):
    dummy_redis = DummyRedis()

    async def fake_from_url(*_args, **_kwargs):  # noqa: ANN001
        return dummy_redis

    async def fake_fastapi_init(client):  # noqa: ANN001
        from fastapi_limiter import FastAPILimiter

        FastAPILimiter.redis = client

    fake_engine = SimpleNamespace(dispose=lambda: None)

    monkeypatch.setattr("backend.main.redis.from_url", fake_from_url)
    monkeypatch.setattr("backend.main.FastAPILimiter.init", fake_fastapi_init)
    monkeypatch.setattr("backend.main.log_api_integration_report", lambda: asyncio.sleep(0))
    mock_user_service = SimpleNamespace(ensure_user=lambda *_: None)
    monkeypatch.setattr("backend.main.user_service", mock_user_service)
    monkeypatch.setattr("backend.services.user_service.user_service", mock_user_service)
    monkeypatch.setattr(Base.metadata, "create_all", lambda **_: None)
    monkeypatch.setattr("backend.database.engine", fake_engine)

    caplog.set_level("INFO")
    caplog.clear()
    async with app.router.lifespan_context(app):
        pass

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "fastapi_limiter_initialized" in messages
    assert "redis_closed" in messages
    assert "engine_disposed" in messages
    assert dummy_redis.pings == 1
    assert dummy_redis.closed is True


@pytest.mark.asyncio
async def test_lifespan_skips_create_all_outside_local(monkeypatch: pytest.MonkeyPatch):
    fake_metadata = SimpleNamespace(create_all=lambda **_: pytest.fail("create_all should not run"))
    dummy_redis = DummyRedis()

    async def fake_from_url(*_args, **_kwargs):  # noqa: ANN001
        return dummy_redis

    monkeypatch.setattr("backend.main.ENV", "production")
    monkeypatch.setattr(Base, "metadata", fake_metadata)
    monkeypatch.setattr("backend.database.engine", SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr("backend.main.redis.from_url", fake_from_url)
    monkeypatch.setattr("backend.main.FastAPILimiter.init", lambda *_: asyncio.sleep(0))
    mock_user_service = SimpleNamespace(ensure_user=lambda *_: None)
    monkeypatch.setattr("backend.main.user_service", mock_user_service)
    monkeypatch.setattr("backend.services.user_service.user_service", mock_user_service)
    monkeypatch.setattr("backend.main.log_api_integration_report", lambda: asyncio.sleep(0))

    async with app.router.lifespan_context(app):
        pass


@pytest.mark.asyncio
async def test_lifespan_handles_redis_initialization_error(monkeypatch: pytest.MonkeyPatch, caplog):
    async def failing_from_url(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("redis down")

    monkeypatch.setattr("backend.main.redis.from_url", failing_from_url)
    mock_user_service = SimpleNamespace(ensure_user=lambda *_: None)
    monkeypatch.setattr("backend.main.user_service", mock_user_service)
    monkeypatch.setattr("backend.services.user_service.user_service", mock_user_service)
    monkeypatch.setattr(Base.metadata, "create_all", lambda **_: None)
    monkeypatch.setattr("backend.database.engine", SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr("backend.main.FastAPILimiter.init", lambda *_: asyncio.sleep(0))
    monkeypatch.setattr("backend.main.log_api_integration_report", lambda: asyncio.sleep(0))

    caplog.clear()
    async with app.router.lifespan_context(app):
        pass

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "fastapi_limiter_unavailable" in messages
