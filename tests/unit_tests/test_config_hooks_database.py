import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.database import apply_database_env_overrides


DATABASE_ENV_NAMES = (
    "DATABASE_URL",
    "REPOM_DATABASE_URL",
    "DB_TYPE",
    "SQLALCHEMY_ECHO",
    "SQLALCHEMY_ECHO_LEVEL",
)


@pytest.fixture(autouse=True)
def clear_database_env(monkeypatch):
    for name in DATABASE_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_apply_database_env_overrides_does_nothing_when_unset():
    config = RepomConfig()

    apply_database_env_overrides(config)

    assert config.db_type == "sqlite"
    assert config.db_url != "postgresql://example"
    assert config.enable_sqlalchemy_echo is False
    assert config.sqlalchemy_echo_level == "INFO"


def test_apply_database_env_overrides_applies_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")
    config = RepomConfig()

    apply_database_env_overrides(config)

    assert config.db_url == "postgresql://user:pass@host/db"


def test_apply_database_env_overrides_prefers_repom_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://generic")
    monkeypatch.setenv("REPOM_DATABASE_URL", "postgresql://repom-specific")
    config = RepomConfig()

    apply_database_env_overrides(config)

    assert config.db_url == "postgresql://repom-specific"


def test_apply_database_env_overrides_applies_db_type(monkeypatch):
    monkeypatch.setenv("DB_TYPE", "postgres")
    config = RepomConfig()

    apply_database_env_overrides(config)

    assert config.db_type == "postgres"


def test_apply_database_env_overrides_rejects_invalid_db_type(monkeypatch):
    monkeypatch.setenv("DB_TYPE", "mysql")
    config = RepomConfig()

    with pytest.raises(ValueError, match="Invalid DB_TYPE"):
        apply_database_env_overrides(config)


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_apply_database_env_overrides_enables_sqlalchemy_echo(monkeypatch, value):
    monkeypatch.setenv("SQLALCHEMY_ECHO", value)
    config = RepomConfig()

    apply_database_env_overrides(config)

    assert config.enable_sqlalchemy_echo is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off"])
def test_apply_database_env_overrides_disables_sqlalchemy_echo(monkeypatch, value):
    monkeypatch.setenv("SQLALCHEMY_ECHO", value)
    config = RepomConfig()
    config.enable_sqlalchemy_echo = True

    apply_database_env_overrides(config)

    assert config.enable_sqlalchemy_echo is False


def test_apply_database_env_overrides_rejects_invalid_sqlalchemy_echo(monkeypatch):
    monkeypatch.setenv("SQLALCHEMY_ECHO", "sometimes")
    config = RepomConfig()

    with pytest.raises(ValueError, match="SQLALCHEMY_ECHO must be a boolean value"):
        apply_database_env_overrides(config)


def test_apply_database_env_overrides_applies_sqlalchemy_echo_level(monkeypatch):
    monkeypatch.setenv("SQLALCHEMY_ECHO_LEVEL", "DEBUG")
    config = RepomConfig()

    apply_database_env_overrides(config)

    assert config.sqlalchemy_echo_level == "DEBUG"


def test_apply_database_env_overrides_rejects_invalid_sqlalchemy_echo_level(
    monkeypatch,
):
    monkeypatch.setenv("SQLALCHEMY_ECHO_LEVEL", "TRACE")
    config = RepomConfig()

    with pytest.raises(ValueError, match="Invalid log level"):
        apply_database_env_overrides(config)


def test_repom_config_singleton_applies_database_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("REPOM_DATABASE_URL", "postgresql://repom-specific")
    monkeypatch.setenv("DB_TYPE", "postgres")
    monkeypatch.setenv("SQLALCHEMY_ECHO", "true")
    monkeypatch.setenv("SQLALCHEMY_ECHO_LEVEL", "DEBUG")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.db_type == "postgres"
        assert reloaded.config.db_url == "postgresql://repom-specific"
        assert reloaded.config.enable_sqlalchemy_echo is True
        assert reloaded.config.sqlalchemy_echo_level == "DEBUG"
    finally:
        for name in DATABASE_ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)
