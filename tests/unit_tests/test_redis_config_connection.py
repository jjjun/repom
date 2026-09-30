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
