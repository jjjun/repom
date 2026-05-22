import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides


PGADMIN_ENV_NAMES = (
    "PGADMIN_DEFAULT_EMAIL",
    "PGADMIN_DEFAULT_PASSWORD",
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
    config = RepomConfig()

    apply_pgadmin_env_overrides(config)

    assert config.pgadmin.email == "admin@repom.local"
    assert config.pgadmin.password == "secret"


def test_repom_config_singleton_applies_pgadmin_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("PGADMIN_DEFAULT_EMAIL", "env-admin@repom.local")
    monkeypatch.setenv("PGADMIN_DEFAULT_PASSWORD", "env-secret")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.pgadmin.email == "env-admin@repom.local"
        assert reloaded.config.pgadmin.password == "env-secret"
    finally:
        for name in PGADMIN_ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)
