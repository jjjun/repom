from dataclasses import dataclass
import importlib

import pytest

from repom.config import RepomConfig
from repom.config_hooks.redis import apply_redis_env_overrides


def test_apply_redis_env_overrides_does_nothing_when_unset(monkeypatch):
    monkeypatch.delenv("REDIS_PORT", raising=False)
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert config.redis.port == 6379


def test_apply_redis_env_overrides_applies_port(monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "6381")
    config = RepomConfig()

    apply_redis_env_overrides(config)

    assert config.redis.port == 6381


def test_apply_redis_env_overrides_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "invalid")
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_PORT must be an integer"):
        apply_redis_env_overrides(config)


@pytest.mark.parametrize("value", ["0", "70000"])
def test_apply_redis_env_overrides_rejects_out_of_range(monkeypatch, value):
    monkeypatch.setenv("REDIS_PORT", value)
    config = RepomConfig()

    with pytest.raises(ValueError, match="REDIS_PORT must be between 1 and 65535"):
        apply_redis_env_overrides(config)


def test_apply_redis_env_overrides_ignores_config_without_redis(monkeypatch):
    @dataclass
    class ConfigWithoutRedis:
        name: str = "test"

    monkeypatch.setenv("REDIS_PORT", "6381")

    apply_redis_env_overrides(ConfigWithoutRedis())


def test_repom_config_singleton_applies_redis_port_env(monkeypatch):
    import repom.config as config_module

    monkeypatch.setenv("REDIS_PORT", "6390")
    reloaded = importlib.reload(config_module)

    try:
        assert reloaded.config.redis.port == 6390
    finally:
        monkeypatch.delenv("REDIS_PORT", raising=False)
        importlib.reload(config_module)
