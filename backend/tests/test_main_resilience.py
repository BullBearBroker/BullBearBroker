from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

from backend.core import tracing
from backend.database import Base
from backend.main import app
from backend.utils.config import Config


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
async def test_lifespan_records_startup_and_shutdown_logs(
    monkeypatch: pytest.MonkeyPatch, caplog
):
    dummy_redis = DummyRedis()

    async def fake_from_url(*_args, **_kwargs):  # noqa: ANN001
        return dummy_redis

    async def fake_fastapi_init(client):  # noqa: ANN001
        from fastapi_limiter import FastAPILimiter

        FastAPILimiter.redis = client

    fake_engine = SimpleNamespace(dispose=lambda: None)

    monkeypatch.setattr("backend.main.redis.from_url", fake_from_url)
    monkeypatch.setattr("backend.main.FastAPILimiter.init", fake_fastapi_init)
    monkeypatch.setattr(
        "backend.main.log_api_integration_report", lambda: asyncio.sleep(0)
    )
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
    assert "engine_disposed" in messages or "engine_dispose_error" in messages
    assert dummy_redis.pings == 1
    assert dummy_redis.closed is True


@pytest.mark.asyncio
async def test_lifespan_skips_create_all_outside_local(monkeypatch: pytest.MonkeyPatch):
    fake_metadata = SimpleNamespace(
        create_all=lambda **_: pytest.fail("create_all should not run")
    )
    dummy_redis = DummyRedis()

    async def fake_from_url(*_args, **_kwargs):  # noqa: ANN001
        return dummy_redis

    monkeypatch.setattr("backend.main.ENV", "production")
    monkeypatch.setattr(Base, "metadata", fake_metadata)
    monkeypatch.setattr(
        "backend.database.engine", SimpleNamespace(dispose=lambda: None)
    )
    monkeypatch.setattr("backend.main.redis.from_url", fake_from_url)
    monkeypatch.setattr("backend.main.FastAPILimiter.init", lambda *_: asyncio.sleep(0))
    mock_user_service = SimpleNamespace(ensure_user=lambda *_: None)
    monkeypatch.setattr("backend.main.user_service", mock_user_service)
    monkeypatch.setattr("backend.services.user_service.user_service", mock_user_service)
    monkeypatch.setattr(
        "backend.main.log_api_integration_report", lambda: asyncio.sleep(0)
    )

    async with app.router.lifespan_context(app):
        pass


@pytest.mark.asyncio
async def test_lifespan_handles_redis_initialization_error(
    monkeypatch: pytest.MonkeyPatch, caplog
):
    async def failing_from_url(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("redis down")

    monkeypatch.setattr("backend.main.redis.from_url", failing_from_url)
    mock_user_service = SimpleNamespace(ensure_user=lambda *_: None)
    monkeypatch.setattr("backend.main.user_service", mock_user_service)
    monkeypatch.setattr("backend.services.user_service.user_service", mock_user_service)
    monkeypatch.setattr(Base.metadata, "create_all", lambda **_: None)
    monkeypatch.setattr(
        "backend.database.engine", SimpleNamespace(dispose=lambda: None)
    )
    monkeypatch.setattr("backend.main.FastAPILimiter.init", lambda *_: asyncio.sleep(0))
    monkeypatch.setattr(
        "backend.main.log_api_integration_report", lambda: asyncio.sleep(0)
    )

    caplog.clear()
    async with app.router.lifespan_context(app):
        pass

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "fastapi_limiter_unavailable" in messages


@pytest.mark.asyncio
async def test_lifespan_logs_database_setup_error(
    monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    dummy_redis = DummyRedis()

    async def fake_from_url(*_args, **_kwargs):  # noqa: ANN001
        return dummy_redis

    class _Engine:
        def __init__(self) -> None:
            self.disposed = False

        def dispose(self):
            self.disposed = True

    fake_engine = _Engine()

    monkeypatch.setattr("backend.main.redis.from_url", fake_from_url)
    monkeypatch.setattr("backend.main.FastAPILimiter.init", lambda *_: asyncio.sleep(0))
    monkeypatch.setattr("backend.database.engine", fake_engine)
    monkeypatch.setattr(
        Base.metadata,
        "create_all",
        lambda **_: (_ for _ in ()).throw(RuntimeError("db offline")),
    )
    mock_user_service = SimpleNamespace(ensure_user=lambda *_: None)
    monkeypatch.setattr("backend.main.user_service", mock_user_service)
    monkeypatch.setattr("backend.services.user_service.user_service", mock_user_service)
    monkeypatch.setattr(
        "backend.main.log_api_integration_report", lambda: asyncio.sleep(0)
    )

    caplog.clear()
    async with app.router.lifespan_context(app):
        pass

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "database_setup_error" in messages
    assert fake_engine.disposed is True


@pytest.mark.asyncio
async def test_tracing_configuration_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    tracing.reset_tracing_state_for_tests()

    monkeypatch.setattr(Config, "ENABLE_TRACING", True, raising=False)
    monkeypatch.setattr(Config, "OTEL_SERVICE_NAME", "test-service", raising=False)
    monkeypatch.setattr(Config, "OTEL_EXPORTER_OTLP_ENDPOINT", None, raising=False)
    monkeypatch.setattr(
        Config, "OTEL_EXPORTER_OTLP_HEADERS", "x-token=abc", raising=False
    )
    monkeypatch.setattr(Config, "OTEL_EXPORTER_OTLP_TIMEOUT", 5, raising=False)

    class DummyResource:
        def __init__(self, attributes):
            self.attributes = dict(attributes)

        @classmethod
        def create(cls, attributes):
            return cls(attributes)

        def merge(self, other):
            merged = dict(self.attributes)
            merged.update(getattr(other, "attributes", {}))
            return DummyResource(merged)

    class DummyTracerProvider:
        def __init__(self, resource=None):
            self.resource = resource
            self.processors: list = []

        def add_span_processor(self, processor):  # noqa: ANN001 - mimic OTEL API
            self.processors.append(processor)

    class DummyTrace:
        def __init__(self) -> None:
            self.provider = None

        def get_tracer_provider(self):  # noqa: D401 - mimic OTEL API
            return self.provider

        def set_tracer_provider(self, provider):  # noqa: D401 - mimic OTEL API
            self.provider = provider

    trace_module = DummyTrace()
    instrumentation_calls: list = []

    class DummyFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app, tracer_provider=None):  # noqa: ANN001 - mimic OTEL API
            instrumentation_calls.append((app, tracer_provider))

    class DummyHTTPXClientInstrumentor:
        def __init__(self) -> None:
            self._instrumented = False

        def instrument(self, tracer_provider=None):  # noqa: ANN001 - mimic OTEL API
            self._instrumented = True
            instrumentation_calls.append(("httpx", tracer_provider))

        def uninstrument(self) -> None:
            self._instrumented = False

    class DummyBatchSpanProcessor:
        def __init__(self, exporter) -> None:  # noqa: ANN001 - mimic OTEL API
            self.exporter = exporter

    class DummyExporter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(
        tracing,
        "_load_tracing_dependencies",
        lambda: (
            trace_module,
            DummyFastAPIInstrumentor,
            DummyHTTPXClientInstrumentor,
            DummyResource,
            DummyTracerProvider,
            DummyBatchSpanProcessor,
            DummyExporter,
        ),
    )

    configured = tracing.configure_tracing(app)
    assert configured is True
    assert instrumentation_calls[0][0] is app
    tracer_provider = instrumentation_calls[0][1]
    assert isinstance(tracer_provider, DummyTracerProvider)
    assert instrumentation_calls[1] == ("httpx", tracer_provider)
    assert tracer_provider.processors
    exporter_kwargs = tracer_provider.processors[0].exporter.kwargs
    assert exporter_kwargs["timeout"] == 5
    assert exporter_kwargs["headers"] == {"x-token": "abc"}

    assert tracing.configure_tracing(app) is False

    tracing.reset_tracing_state_for_tests()
