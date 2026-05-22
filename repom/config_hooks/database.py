"""Database config hook helpers."""

from __future__ import annotations

import os
from typing import Any

from repom.config_hooks._parsing import parse_bool_env


def apply_database_env_overrides(config: Any) -> None:
    """Apply database runtime overrides from environment variables.

    Reads: REPOM_DATABASE_URL, DATABASE_URL, DB_TYPE, SQLALCHEMY_ECHO,
    SQLALCHEMY_ECHO_LEVEL.
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


__all__ = [
    "apply_database_env_overrides",
]
