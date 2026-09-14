"""Tests that credential-bearing dataclasses never leak passwords via repr/str.

``repr(config)``, ``str(config)``, a bare logger call, and an unhandled
traceback frame all end up calling ``repr()`` on config objects. These tests
lock in that PostgresConfig, PgAdminConfig, RedisConfig and PgConnParams
mask their password field instead of printing it in the clear.

Note: ``dataclasses.asdict()`` (and ``vars()``) bypass ``__repr__`` entirely
and always return the raw field values, regardless of ``repr=False``. That is
a stdlib limitation with no per-field hook to intercept, so it is out of
scope here; code that must serialize config for logging should render it via
``repr()``/``str()``, not ``asdict()``.
"""

from repom.config import RepomConfig
from repom.postgres.config import PgAdminConfig, PostgresConfig
from repom.redis.config import RedisConfig
from repom.scripts.pg_dump_tools import PgConnParams


def test_postgres_config_repr_masks_password():
    sentinel = "postgres-sentinel"
    config = PostgresConfig(password=sentinel)

    result = repr(config)

    assert sentinel not in result
    assert "***" in result
    assert "localhost" in result


def test_pgadmin_config_repr_masks_password():
    sentinel = "pgadmin-sentinel"
    config = PgAdminConfig(password=sentinel)

    result = repr(config)

    assert sentinel not in result
    assert "***" in result


def test_redis_config_repr_masks_password():
    sentinel = "redis-sentinel"
    config = RedisConfig(password=sentinel)

    result = repr(config)

    assert sentinel not in result
    assert "***" in result


def test_redis_config_repr_shows_none_when_unset():
    config = RedisConfig(password=None)

    assert "password=None" in repr(config)
    assert "***" not in repr(config)


def test_config_repr_masks_all_passwords():
    """repr(config) and str(config) must mask postgres, pgadmin and redis passwords."""
    postgres_sentinel = "postgres-sentinel"
    pgadmin_sentinel = "pgadmin-sentinel"
    redis_sentinel = "redis-sentinel"

    config = RepomConfig()
    config.postgres.password = postgres_sentinel
    config.pgadmin.password = pgadmin_sentinel
    config.redis.password = redis_sentinel

    rendered_repr = repr(config)
    rendered_str = str(config)

    for sentinel in (postgres_sentinel, pgadmin_sentinel, redis_sentinel):
        assert sentinel not in rendered_repr
        assert sentinel not in rendered_str

    assert rendered_repr.count("***") == 3


def test_pg_conn_params_repr_masks_password():
    sentinel = "pgconn-sentinel"
    params = PgConnParams(
        host="localhost",
        port=5432,
        user="repom",
        password=sentinel,
        database="repom",
    )

    result = repr(params)

    assert sentinel not in result
    assert "***" in result
    assert "localhost" in result


def test_pg_conn_params_repr_shows_none_when_unset():
    params = PgConnParams(
        host="localhost",
        port=5432,
        user="repom",
        password=None,
        database="repom",
    )

    assert "password=None" in repr(params)
    assert "***" not in repr(params)
