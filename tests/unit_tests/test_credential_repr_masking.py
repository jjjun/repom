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
from repom.postgres.credentials import (
    PgAdminCredentialRotationPlan,
    PostgresCredentialRotationPlan,
    build_postgres_rotation_steps,
)
from repom.redis.config import RedisConfig
from repom.redis.credentials import RedisCredentialRotationPlan
from repom.scripts.pg_dump_tools import PgConnParams


def test_postgres_config_repr_masks_password():
    sentinel = "postgres-sentinel"
    config = PostgresConfig(password=sentinel)

    result = repr(config)

    assert sentinel not in result
    assert "***" in result
    assert "127.0.0.1" in result


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


def test_rotation_plan_representations_hide_password_fields():
    plans_and_secrets = (
        (
            PostgresCredentialRotationPlan(
                current_user="repom",
                current_password="current-password-sentinel",
                new_password="new-password-sentinel",
            ),
            ("current-password-sentinel", "new-password-sentinel"),
        ),
        (
            PgAdminCredentialRotationPlan(
                email="admin@example.com",
                new_password="new-password-sentinel",
            ),
            ("new-password-sentinel",),
        ),
        (
            RedisCredentialRotationPlan(
                old_password="old-password-sentinel",
                new_password="new-password-sentinel",
            ),
            ("old-password-sentinel", "new-password-sentinel"),
        ),
    )

    for plan, secrets in plans_and_secrets:
        for representation in (repr(plan), str(plan)):
            for secret in secrets:
                assert secret not in representation


def test_rotation_plan_password_fields_remain_accessible():
    postgres_plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="current-password-sentinel",
        new_password="new-password-sentinel",
    )
    pgadmin_plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="new-password-sentinel",
    )
    redis_plan = RedisCredentialRotationPlan(
        old_password="old-password-sentinel",
        new_password="new-password-sentinel",
    )

    assert postgres_plan.current_password == "current-password-sentinel"
    assert postgres_plan.new_password == "new-password-sentinel"
    assert pgadmin_plan.new_password == "new-password-sentinel"
    assert redis_plan.old_password == "old-password-sentinel"
    assert redis_plan.new_password == "new-password-sentinel"


def test_postgres_rotation_sql_step_repr_hides_password_but_preserves_sql():
    password = "new-password-sentinel"
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        new_user="repom_new",
        new_password=password,
    )
    step = build_postgres_rotation_steps(plan)[0]

    assert password in step.sql
    assert password not in repr(step)
    assert password not in str(step)
