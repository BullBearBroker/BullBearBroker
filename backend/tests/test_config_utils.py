import importlib

import pytest

from backend.utils import config as config_module


def test_get_env_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BULLBEAR_SAMPLE", "  value  ")
    assert config_module._get_env("BULLBEAR_SAMPLE") == "value"

    monkeypatch.setenv("BULLBEAR_SAMPLE", "   ")
    assert config_module._get_env("BULLBEAR_SAMPLE") is None


def test_require_env_logs_and_raises(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.delenv("BULLBEAR_MISSING", raising=False)
    caplog.set_level("ERROR")

    with pytest.raises(RuntimeError):
        config_module._require_env("BULLBEAR_MISSING")

    assert "Missing required environment variable" in caplog.text


def test_config_require_env_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BULLBEAR_PRESENT", "present")

    # Recargar módulo para asegurar que los cambios de entorno se respetan
    importlib.reload(config_module)

    assert config_module.Config.require_env("BULLBEAR_PRESENT") == "present"
