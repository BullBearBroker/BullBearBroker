import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _reload_database(monkeypatch: pytest.MonkeyPatch, env_value: str):
    monkeypatch.setenv("ENV", env_value)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///memory.db")
    monkeypatch.delenv("BULLBEAR_SKIP_AUTOCREATE", raising=False)

    create_engine_mock = MagicMock(return_value="engine")
    sessionmaker_mock = MagicMock(return_value="session_factory")
    inspect_stub = MagicMock(
        return_value=SimpleNamespace(
            get_table_names=lambda: [],
            get_columns=lambda _name: [],
        )
    )
    text_mock = MagicMock()

    monkeypatch.setattr("sqlalchemy.create_engine", create_engine_mock)
    monkeypatch.setattr("sqlalchemy.orm.sessionmaker", sessionmaker_mock)
    monkeypatch.setattr("sqlalchemy.inspect", inspect_stub)
    monkeypatch.setattr("sqlalchemy.text", text_mock)

    package_stub = ModuleType("backend")
    package_stub.__path__ = ["/app"]
    monkeypatch.setitem(sys.modules, "backend", package_stub)

    base_stub = ModuleType("backend.models.base")
    create_all_mock = MagicMock()
    base_stub.Base = SimpleNamespace(metadata=SimpleNamespace(create_all=create_all_mock))
    monkeypatch.setitem(sys.modules, "backend.models.base", base_stub)

    for module_name in ("backend.database", "backend.utils.config"):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("backend.database")
    return module, create_all_mock


def test_create_all_runs_only_in_local(monkeypatch: pytest.MonkeyPatch):
    _, create_all_mock = _reload_database(monkeypatch, "local")
    assert create_all_mock.call_count == 1


def test_create_all_skipped_outside_local(monkeypatch: pytest.MonkeyPatch):
    _, create_all_mock = _reload_database(monkeypatch, "staging")
    assert create_all_mock.call_count == 0
