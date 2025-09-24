"""Utility helpers to stub optional dependencies during tests."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import os
import sys
import types
from types import SimpleNamespace


_EMAIL_METADATA_PATCHED = False


def ensure() -> None:
    """Install lightweight stubs for optional packages used by the app."""

    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/testdb")

    if "passlib.context" not in sys.modules:
        class _FakeCryptContext:  # pragma: no cover - stub for tests
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def hash(self, password: str) -> str:
                return f"hashed-{password}"

            def verify(self, password: str, hashed: str) -> bool:
                return hashed in {password, f"hashed-{password}"}

        passlib_module = types.ModuleType("passlib")
        passlib_context_module = types.ModuleType("passlib.context")
        passlib_context_module.CryptContext = _FakeCryptContext
        passlib_module.context = passlib_context_module  # type: ignore[attr-defined]
        sys.modules["passlib"] = passlib_module
        sys.modules["passlib.context"] = passlib_context_module

    global _EMAIL_METADATA_PATCHED
    if "email_validator" not in sys.modules:
        email_validator_module = types.ModuleType("email_validator")

        class _EmailNotValidError(ValueError):  # pragma: no cover - stub
            pass

        def _validate_email(value: str, *_args, **_kwargs):  # pragma: no cover - stub
            local_part = value.split("@", 1)[0]
            return SimpleNamespace(email=value, normalized=value.lower(), local_part=local_part)

        email_validator_module.EmailNotValidError = _EmailNotValidError  # type: ignore[attr-defined]
        email_validator_module.validate_email = _validate_email  # type: ignore[attr-defined]
        sys.modules["email_validator"] = email_validator_module

    if not _EMAIL_METADATA_PATCHED:
        original_version = importlib_metadata.version

        def _version(name: str) -> str:  # pragma: no cover - stubbed helper
            if name == "email-validator":
                return "2.0.0"
            return original_version(name)

        importlib_metadata.version = _version  # type: ignore[assignment]
        _EMAIL_METADATA_PATCHED = True

    if "psycopg" not in sys.modules:
        psycopg_module = types.ModuleType("psycopg")
        psycopg_module.paramstyle = "pyformat"  # type: ignore[attr-defined]
        psycopg_module.__version__ = "3.1.0"  # type: ignore[attr-defined]

        def _connect(*_args, **_kwargs):  # pragma: no cover - stub
            raise RuntimeError("Database connections are disabled in tests")

        psycopg_module.connect = _connect  # type: ignore[attr-defined]

        psycopg_adapt_module = types.ModuleType("psycopg.adapt")

        class _AdaptersMap:  # pragma: no cover - stub
            def __init__(self, *_args, **_kwargs) -> None:
                self.adapters = {}

        psycopg_adapt_module.AdaptersMap = _AdaptersMap  # type: ignore[attr-defined]
        psycopg_module.adapt = psycopg_adapt_module  # type: ignore[attr-defined]
        psycopg_module.adapters = psycopg_adapt_module  # type: ignore[attr-defined]
        sys.modules["psycopg"] = psycopg_module
        sys.modules["psycopg.adapt"] = psycopg_adapt_module
