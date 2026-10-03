import pytest

from repom.config import RepomConfig
from repom.redis.config import RedisConfig, RedisContainerConfig


def test_redis_connection_kwargs_use_connection_port_and_omit_empty_password():
    config = RedisConfig(
        host="redis.local",
        port=6381,
        database=3,
        password="",
        container=RedisContainerConfig(host_port=6390),
    )

    assert config.connection_kwargs() == {
        "host": "redis.local",
        "port": 6381,
        "db": 3,
        "password": None,
    }


def test_redis_url_without_password():
    config = RedisConfig(host="redis.local", port=6381, database=3)

    assert config.url() == "redis://redis.local:6381/3"
    assert config.url(include_password=True) == "redis://redis.local:6381/3"
    assert config.safe_url() == "redis://redis.local:6381/3"


def test_redis_url_can_include_encoded_password_and_safe_url_masks_it():
    config = RedisConfig(
        host="redis.local",
        port=6381,
        database=3,
        password="a p@ss/word",
    )

    assert config.url() == "redis://redis.local:6381/3"
    assert config.connection_kwargs() == {
        "host": "redis.local",
        "port": 6381,
        "db": 3,
        "password": "a p@ss/word",
    }
    assert config.url(include_password=True) == (
        "redis://:a%20p%40ss%2Fword@redis.local:6381/3"
    )
    assert config.safe_url() == "redis://:***@redis.local:6381/3"


@pytest.mark.parametrize(
    "host",
    ["localhost", "LOCALHOST.", "127.0.0.1", "127.42.0.1", "::1", "[::1]"],
)
def test_repom_redis_connection_kwargs_allow_local_production_hosts(host):
    config = RepomConfig(exec_env="production")
    config.redis.host = host

    assert config.redis_connection_kwargs() == config.redis.connection_kwargs()


@pytest.mark.parametrize("exec_env", ["prod", " Production "])
def test_repom_redis_connection_kwargs_reject_remote_production_host(exec_env):
    config = RepomConfig(exec_env=exec_env)
    config.redis.host = "redis"

    with pytest.raises(ValueError, match="REDIS_ALLOW_INSECURE_REMOTE=true"):
        config.redis_connection_kwargs()


def test_repom_redis_connection_kwargs_allow_opted_in_remote_production_host():
    config = RepomConfig(exec_env="prod")
    config.redis.host = "redis"
    config.redis.allow_insecure_remote = True

    assert config.redis_connection_kwargs() == config.redis.connection_kwargs()


@pytest.mark.parametrize("exec_env", ["dev", "test"])
def test_repom_redis_connection_kwargs_keep_nonproduction_remote_behavior(exec_env):
    config = RepomConfig(exec_env=exec_env)
    config.redis.host = "redis"

    assert config.redis_connection_kwargs() == config.redis.connection_kwargs()
