import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.sqlite import apply_sqlite_env_overrides


SQLITE_ENV_NAMES = (
    "SQLITE_DB_PATH",
    "SQLITE_DB_FILE",
    "SQLITE_USE_IN_MEMORY_FOR_TESTS",
    "SQLITE_USE_FILE_DB",
)


@pytest.fixture(autouse=True)
def clear_sqlite_env(monkeypatch):
    for name in SQLITE_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_apply_sqlite_env_overrides_does_nothing_when_unset():
    config = RepomConfig()

    apply_sqlite_env_overrides(config)

    assert config.sqlite.db_file == "repom_test.sqlite3"
    assert config.sqlite.use_in_memory_for_tests is True


def test_apply_sqlite_env_overrides_applies_db_path_and_file(monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", "custom/data")
    monkeypatch.setenv("SQLITE_DB_FILE", "custom.sqlite3")
    config = RepomConfig()

    apply_sqlite_env_overrides(config)

    assert config.sqlite.db_path == "custom/data"
    assert config.sqlite.db_file == "custom.sqlite3"


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_apply_sqlite_env_overrides_enables_in_memory_tests(monkeypatch, value):
    monkeypatch.setenv("SQLITE_USE_IN_MEMORY_FOR_TESTS", value)
    config = RepomConfig()
    config.sqlite.use_in_memory_for_tests = False

    apply_sqlite_env_overrides(config)

    assert config.sqlite.use_in_memory_for_tests is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off"])
def test_apply_sqlite_env_overrides_disables_in_memory_tests(monkeypatch, value):
    monkeypatch.setenv("SQLITE_USE_IN_MEMORY_FOR_TESTS", value)
    config = RepomConfig()

    apply_sqlite_env_overrides(config)

    assert config.sqlite.use_in_memory_for_tests is False


def test_apply_sqlite_env_overrides_rejects_invalid_in_memory_bool(monkeypatch):
    monkeypatch.setenv("SQLITE_USE_IN_MEMORY_FOR_TESTS", "sometimes")
    config = RepomConfig()

    with pytest.raises(
        ValueError,
        match="SQLITE_USE_IN_MEMORY_FOR_TESTS must be a boolean value",
    ):
        apply_sqlite_env_overrides(config)


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_apply_sqlite_env_overrides_supports_legacy_use_file_db(monkeypatch, value):
    monkeypatch.setenv("SQLITE_USE_FILE_DB", value)
    config = RepomConfig()

    apply_sqlite_env_overrides(config)

    assert config.sqlite.use_in_memory_for_tests is False


def test_apply_sqlite_env_overrides_ignores_config_without_sqlite(monkeypatch):
    class ConfigWithoutSqlite:
        pass

    monkeypatch.setenv("SQLITE_DB_FILE", "custom.sqlite3")

    apply_sqlite_env_overrides(ConfigWithoutSqlite())


def test_repom_config_singleton_applies_sqlite_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("SQLITE_DB_PATH", "env/data")
    monkeypatch.setenv("SQLITE_DB_FILE", "env.sqlite3")
    monkeypatch.setenv("SQLITE_USE_IN_MEMORY_FOR_TESTS", "false")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.sqlite.db_path == "env/data"
        assert reloaded.config.sqlite.db_file == "env.sqlite3"
        assert reloaded.config.sqlite.use_in_memory_for_tests is False
    finally:
        for name in SQLITE_ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)
