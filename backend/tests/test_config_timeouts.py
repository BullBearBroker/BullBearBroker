import os
from importlib import reload
from types import SimpleNamespace

import pytest

import backend.database as database_module
import backend.services.timeseries_service as timeseries_service


@pytest.fixture
def anyio_backend() -> str:
    """Ensure AnyIO uses asyncio backend where httpx AsyncClient is supported."""

    return "asyncio"


def test_database_engine_respects_pool_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_calls: dict[str, dict] = {}

    def fake_create_engine(url: str, **kwargs):  # noqa: ANN001 - mimic SQLAlchemy API
        create_calls["kwargs"] = kwargs
        return SimpleNamespace(dispose=lambda: None)

    with monkeypatch.context() as context:
        context.setenv("BULLBEAR_SKIP_AUTOCREATE", "1")
        context.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        context.setattr("sqlalchemy.create_engine", fake_create_engine)
        context.setattr(database_module.Config, "DB_POOL_SIZE", 7, raising=False)
        context.setattr(database_module.Config, "DB_MAX_OVERFLOW", 2, raising=False)
        context.setattr(database_module.Config, "DB_POOL_RECYCLE", 123, raising=False)
        context.setattr(database_module.Config, "DB_POOL_TIMEOUT", 9, raising=False)

        reload(database_module)

        kwargs = create_calls["kwargs"]
        assert kwargs["pool_size"] == 7
        assert kwargs["max_overflow"] == 2
        assert kwargs["pool_recycle"] == 123
        assert kwargs["pool_timeout"] == 9

    original_db_url = os.environ.get("DATABASE_URL")
    original_skip = os.environ.get("BULLBEAR_SKIP_AUTOCREATE")
    os.environ["DATABASE_URL"] = "sqlite:///./bullbearbroker.db"
    os.environ["BULLBEAR_SKIP_AUTOCREATE"] = "1"
    try:
        reload(database_module)
    finally:
        if original_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_db_url
        if original_skip is None:
            os.environ.pop("BULLBEAR_SKIP_AUTOCREATE", None)
        else:
            os.environ["BULLBEAR_SKIP_AUTOCREATE"] = original_skip


@pytest.mark.anyio
async def test_timeseries_http_timeout_respects_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeseries_service, "_HTTP_TIMEOUT_SECONDS", 3.0, raising=False)
    monkeypatch.setattr(
        timeseries_service, "_HTTP_CONNECT_TIMEOUT_SECONDS", 2.0, raising=False
    )

    recorded: dict[str, object] = {}

    class DummyClient:
        def __init__(self, timeout):
            recorded["timeout"] = timeout

        async def __aenter__(self):  # noqa: D401 - async context manager
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        async def get(self, url, params):  # noqa: ANN001 - mimic AsyncClient
            raise RuntimeError("stop")

    monkeypatch.setattr(
        timeseries_service.httpx,
        "AsyncClient",
        lambda **kwargs: DummyClient(kwargs.get("timeout")),
    )

    with pytest.raises(RuntimeError):
        await timeseries_service._http_get_json("https://example.com", {})

    timeout_obj = recorded["timeout"]
    assert timeout_obj.read == 3.0
    assert timeout_obj.connect == 2.0
