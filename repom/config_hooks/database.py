"""Database config hook helpers."""

from __future__ import annotations

import os
from typing import Any

from repom.config_hooks._parsing import parse_bool_env, parse_int_env


def apply_database_env_overrides(config: Any) -> None:
    """Apply database runtime overrides from environment variables.

    Reads: REPOM_DATABASE_URL, DATABASE_URL, DB_TYPE, SQLALCHEMY_ECHO,
    SQLALCHEMY_ECHO_LEVEL, SQLALCHEMY_POOL_SIZE, SQLALCHEMY_MAX_OVERFLOW,
    SQLALCHEMY_POOL_TIMEOUT, SQLALCHEMY_POOL_RECYCLE, SQLALCHEMY_POOL_PRE_PING.
    """
    db_type = os.getenv("DB_TYPE")
    if db_type is not None:
        config.db_type = db_type

    database_url = os.getenv("REPOM_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url is not None:
        config.db_url = database_url

    raw_echo = os.getenv("SQLALCHEMY_ECHO")
    if raw_echo is not None:
        config.enable_sqlalchemy_echo = parse_bool_env("SQLALCHEMY_ECHO", raw_echo)

    echo_level = os.getenv("SQLALCHEMY_ECHO_LEVEL")
    if echo_level is not None:
        config.sqlalchemy_echo_level = echo_level

    pool_size = os.getenv("SQLALCHEMY_POOL_SIZE")
    if pool_size is not None:
        config.db_pool_size = parse_int_env("SQLALCHEMY_POOL_SIZE", pool_size)

    max_overflow = os.getenv("SQLALCHEMY_MAX_OVERFLOW")
    if max_overflow is not None:
        config.db_max_overflow = parse_int_env("SQLALCHEMY_MAX_OVERFLOW", max_overflow)

    pool_timeout = os.getenv("SQLALCHEMY_POOL_TIMEOUT")
    if pool_timeout is not None:
        config.db_pool_timeout = parse_int_env("SQLALCHEMY_POOL_TIMEOUT", pool_timeout)

    pool_recycle = os.getenv("SQLALCHEMY_POOL_RECYCLE")
    if pool_recycle is not None:
        config.db_pool_recycle = parse_int_env("SQLALCHEMY_POOL_RECYCLE", pool_recycle)

    pool_pre_ping = os.getenv("SQLALCHEMY_POOL_PRE_PING")
    if pool_pre_ping is not None:
        config.db_pool_pre_ping = parse_bool_env(
            "SQLALCHEMY_POOL_PRE_PING", pool_pre_ping
        )


__all__ = [
    "apply_database_env_overrides",
]
