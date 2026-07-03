import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides


PGADMIN_ENV_NAMES = (
    "PGADMIN_DEFAULT_EMAIL",
    "PGADMIN_DEFAULT_PASSWORD",
    "PGADMIN_HOST_PORT",
)


@pytest.fixture(autouse=True)
def clear_pgadmin_env(monkeypatch):
    for name in PGADMIN_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_apply_pgadmin_env_overrides_does_nothing_when_unset():
    config = RepomConfig()

    apply_pgadmin_env_overrides(config)

    assert config.pgadmin.email == "admin@example.com"
    assert config.pgadmin.password == "admin"
    assert config.pgadmin.container.host_port == 5050


def test_apply_pgadmin_env_overrides_keeps_existing_host_port_when_unset():
    config = RepomConfig()
    config.pgadmin.container.host_port = 5051

    apply_pgadmin_env_overrides(config)

    assert config.pgadmin.container.host_port == 5051


@pytest.mark.parametrize(
    ("env_name", "value", "attribute"),
    [
        ("PGADMIN_DEFAULT_EMAIL", "admin@repom.local", "email"),
        ("PGADMIN_DEFAULT_PASSWORD", "secret", "password"),
    ],
)
def test_apply_pgadmin_env_overrides_applies_each_env(
    monkeypatch,
    env_name,
    value,
    attribute,
):
    config = RepomConfig()
    monkeypatch.setenv(env_name, value)

    apply_pgadmin_env_overrides(config)

    assert getattr(config.pgadmin, attribute) == value


def test_apply_pgadmin_env_overrides_applies_all_envs(monkeypatch):
    monkeypatch.setenv("PGADMIN_DEFAULT_EMAIL", "admin@repom.local")
    monkeypatch.setenv("PGADMIN_DEFAULT_PASSWORD", "secret")
    monkeypatch.setenv("PGADMIN_HOST_PORT", "15050")
    config = RepomConfig()

    apply_pgadmin_env_overrides(config)

    assert config.pgadmin.email == "admin@repom.local"
    assert config.pgadmin.password == "secret"
    assert config.pgadmin.container.host_port == 15050


def test_apply_pgadmin_env_overrides_applies_host_port(monkeypatch):
    monkeypatch.setenv("PGADMIN_HOST_PORT", "15050")
    config = RepomConfig()

    apply_pgadmin_env_overrides(config)

    assert config.pgadmin.container.host_port == 15050


def test_apply_pgadmin_env_overrides_rejects_non_integer_host_port(monkeypatch):
    monkeypatch.setenv("PGADMIN_HOST_PORT", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="PGADMIN_HOST_PORT must be an integer"):
        apply_pgadmin_env_overrides(config)


@pytest.mark.parametrize("value", ["0", "70000"])
def test_apply_pgadmin_env_overrides_rejects_out_of_range_host_port(
    monkeypatch,
    value,
):
    monkeypatch.setenv("PGADMIN_HOST_PORT", value)
    config = RepomConfig()

    with pytest.raises(
        ValueError,
        match="PGADMIN_HOST_PORT must be between 1 and 65535",
    ):
        apply_pgadmin_env_overrides(config)


def test_repom_config_singleton_applies_pgadmin_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("PGADMIN_DEFAULT_EMAIL", "env-admin@repom.local")
    monkeypatch.setenv("PGADMIN_DEFAULT_PASSWORD", "env-secret")
    monkeypatch.setenv("PGADMIN_HOST_PORT", "15050")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.pgadmin.email == "env-admin@repom.local"
        assert reloaded.config.pgadmin.password == "env-secret"
        assert reloaded.config.pgadmin.container.host_port == 15050
    finally:
        for name in PGADMIN_ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)
