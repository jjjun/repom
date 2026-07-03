from dataclasses import dataclass
import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.redis import apply_redis_env_overrides


REDIS_ENV_NAMES = (
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "REDIS_DB",
    "REDIS_HOST_PORT",
)


@pytest.fixture(autouse=True)
def clear_redis_env(monkeypatch):
    for name in REDIS_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_apply_redis_env_overrides_does_nothing_when_unset():
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert config.redis.host == "localhost"
    assert config.redis.port == 6379
    assert config.redis.password is None
    assert config.redis.database == 0
    assert config.redis.container.host_port == 6379


def test_apply_redis_env_overrides_keeps_existing_host_port_when_unset():
    config = RepomConfig()
    config.redis.container.host_port = 6380

    apply_redis_env_overrides(config)

    assert config.redis.container.host_port == 6380


def test_apply_redis_env_overrides_applies_port(monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "6381")
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert config.redis.port == 6381


def test_apply_redis_env_overrides_applies_host_port(monkeypatch):
    monkeypatch.setenv("REDIS_HOST_PORT", "6382")
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert config.redis.port == 6379
    assert config.redis.container.host_port == 6382


@pytest.mark.parametrize(
    ("env_name", "value", "attribute", "expected"),
    [
        ("REDIS_HOST", "redis.local", "host", "redis.local"),
        ("REDIS_PASSWORD", "secret", "password", "secret"),
        ("REDIS_DB", "2", "database", 2),
    ],
)
def test_apply_redis_env_overrides_applies_connection_env(
    monkeypatch,
    env_name,
    value,
    attribute,
    expected,
):
    monkeypatch.setenv(env_name, value)
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert getattr(config.redis, attribute) == expected


def test_apply_redis_env_overrides_applies_all_envs(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "redis.local")
    monkeypatch.setenv("REDIS_PORT", "6381")
    monkeypatch.setenv("REDIS_HOST_PORT", "6382")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    monkeypatch.setenv("REDIS_DB", "2")
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert config.redis.host == "redis.local"
    assert config.redis.port == 6381
    assert config.redis.container.host_port == 6382
    assert config.redis.password == "secret"
    assert config.redis.database == 2


def test_apply_redis_env_overrides_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_PORT must be an integer"):
        apply_redis_env_overrides(config)


def test_apply_redis_env_overrides_rejects_non_integer_host_port(monkeypatch):
    monkeypatch.setenv("REDIS_HOST_PORT", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_HOST_PORT must be an integer"):
        apply_redis_env_overrides(config)


@pytest.mark.parametrize("value", ["0", "70000"])
def test_apply_redis_env_overrides_rejects_out_of_range(monkeypatch, value):
    monkeypatch.setenv("REDIS_PORT", value)
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_PORT must be between 1 and 65535"):
        apply_redis_env_overrides(config)


@pytest.mark.parametrize("value", ["0", "70000"])
def test_apply_redis_env_overrides_rejects_out_of_range_host_port(monkeypatch, value):
    monkeypatch.setenv("REDIS_HOST_PORT", value)
    config = RepomConfig()

    with pytest.raises(
        ValueError,
        match="REDIS_HOST_PORT must be between 1 and 65535",
    ):
        apply_redis_env_overrides(config)


def test_apply_redis_env_overrides_rejects_non_integer_db(monkeypatch):
    monkeypatch.setenv("REDIS_DB", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_DB must be an integer"):
        apply_redis_env_overrides(config)


def test_apply_redis_env_overrides_rejects_negative_db(monkeypatch):
    monkeypatch.setenv("REDIS_DB", "-1")
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_DB must be greater than or equal to 0"):
        apply_redis_env_overrides(config)


def test_apply_redis_env_overrides_ignores_config_without_redis(monkeypatch):
    @dataclass
    class ConfigWithoutRedis:
        name: str = "test"

    monkeypatch.setenv("REDIS_PORT", "6381")
    monkeypatch.setenv("REDIS_HOST_PORT", "6382")

    apply_redis_env_overrides(ConfigWithoutRedis())


def test_repom_config_singleton_applies_redis_port_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("REDIS_HOST", "env-redis")
    monkeypatch.setenv("REDIS_PORT", "6390")
    monkeypatch.setenv("REDIS_HOST_PORT", "6391")
    monkeypatch.setenv("REDIS_PASSWORD", "env-secret")
    monkeypatch.setenv("REDIS_DB", "3")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.redis.host == "env-redis"
        assert reloaded.config.redis.port == 6390
        assert reloaded.config.redis.container.host_port == 6391
        assert reloaded.config.redis.password == "env-secret"
        assert reloaded.config.redis.database == 3
    finally:
        for name in REDIS_ENV_NAMES:
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config_module)
