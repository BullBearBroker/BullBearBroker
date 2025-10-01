import pytest
from types import SimpleNamespace

from backend.main import app
from backend.database import engine as real_engine


@pytest.mark.asyncio
async def test_engine_dispose_safety(monkeypatch, caplog):
    fake_engine = SimpleNamespace()
    monkeypatch.setattr(
        "backend.main.database_module.engine", fake_engine, raising=True
    )

    caplog.clear()
    async with app.router.lifespan_context(app):
        pass

    logs = " ".join(record.getMessage() for record in caplog.records)
    assert "engine_dispose_error" in logs

    monkeypatch.setattr(
        "backend.main.database_module.engine", real_engine, raising=True
    )
