import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.postgres import apply_postgres_env_overrides


POSTGRES_ENV_NAMES = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_HOST_PORT",
)


@pytest.fixture(autouse=True)
def clear_postgres_env(monkeypatch):
    for name in POSTGRES_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_apply_postgres_env_overrides_does_nothing_when_unset():
    config = RepomConfig()

    apply_postgres_env_overrides(config)

    assert config.postgres.user == "repom"
    assert config.postgres.password == "repom_dev"
    assert config.postgres.host == "localhost"
    assert config.postgres.port == 5432
    assert config.postgres.container.host_port == 5432


def test_apply_postgres_env_overrides_keeps_existing_host_port_when_unset():
    config = RepomConfig()
    config.postgres.container.host_port = 5433

    apply_postgres_env_overrides(config)

    assert config.postgres.container.host_port == 5433


@pytest.mark.parametrize(
    ("env_name", "value", "attribute", "expected"),
    [
        ("POSTGRES_USER", "app_user", "user", "app_user"),
        ("POSTGRES_PASSWORD", "secret", "password", "secret"),
        ("POSTGRES_HOST", "db.local", "host", "db.local"),
        ("POSTGRES_PORT", "15432", "port", 15432),
    ],
)
def test_apply_postgres_env_overrides_applies_each_env(
    monkeypatch,
    env_name,
    value,
    attribute,
    expected,
):
    config = RepomConfig()
    monkeypatch.setenv(env_name, value)

    apply_postgres_env_overrides(config)

    assert getattr(config.postgres, attribute) == expected


def test_apply_postgres_env_overrides_applies_all_envs(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "app_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_HOST", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "15432")
    monkeypatch.setenv("POSTGRES_HOST_PORT", "5455")
    config = RepomConfig()

    apply_postgres_env_overrides(config)

    assert config.postgres.user == "app_user"
    assert config.postgres.password == "secret"
    assert config.postgres.host == "postgres"
    assert config.postgres.port == 15432
    assert config.postgres.container.host_port == 5455


def test_apply_postgres_env_overrides_applies_host_port_without_connection_port(
    monkeypatch,
):
    monkeypatch.setenv("POSTGRES_HOST_PORT", "5455")
    config = RepomConfig()

    apply_postgres_env_overrides(config)

    assert config.postgres.port == 5432
    assert config.postgres.container.host_port == 5455


def test_apply_postgres_env_overrides_rejects_non_integer_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="POSTGRES_PORT must be an integer"):
        apply_postgres_env_overrides(config)


def test_apply_postgres_env_overrides_rejects_non_integer_host_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST_PORT", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="POSTGRES_HOST_PORT must be an integer"):
        apply_postgres_env_overrides(config)


@pytest.mark.parametrize("value", ["0", "70000"])
def test_apply_postgres_env_overrides_rejects_out_of_range_port(
    monkeypatch,
    value,
):
    monkeypatch.setenv("POSTGRES_PORT", value)
    config = RepomConfig()

    with pytest.raises(ValueError, match="POSTGRES_PORT must be between 1 and 65535"):
        apply_postgres_env_overrides(config)


@pytest.mark.parametrize("value", ["0", "70000"])
def test_apply_postgres_env_overrides_rejects_out_of_range_host_port(
    monkeypatch,
    value,
):
    monkeypatch.setenv("POSTGRES_HOST_PORT", value)
    config = RepomConfig()

    with pytest.raises(
        ValueError,
        match="POSTGRES_HOST_PORT must be between 1 and 65535",
    ):
        apply_postgres_env_overrides(config)


def test_repom_config_singleton_applies_postgres_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("POSTGRES_USER", "env_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "env_password")
    monkeypatch.setenv("POSTGRES_HOST", "env-postgres")
    monkeypatch.setenv("POSTGRES_PORT", "15432")
    monkeypatch.setenv("POSTGRES_HOST_PORT", "5455")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.postgres.user == "env_user"
        assert reloaded.config.postgres.password == "env_password"
        assert reloaded.config.postgres.host == "env-postgres"
        assert reloaded.config.postgres.port == 15432
        assert reloaded.config.postgres.container.host_port == 5455
    finally:
        for name in POSTGRES_ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)
