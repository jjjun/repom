"""Redis config hook helpers."""

from __future__ import annotations

import os
from typing import Any

from repom.config_hooks._parsing import parse_int_env, parse_port_env


def apply_redis_env_overrides(config: Any) -> None:
    """Apply Redis runtime overrides from environment variables.

    Reads: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, REDIS_HOST_PORT.
    """
    redis = getattr(config, "redis", None)
    if redis is None:
        return

    host = os.getenv("REDIS_HOST")
    if host is not None:
        redis.host = host

    password = os.getenv("REDIS_PASSWORD")
    if password is not None:
        redis.password = password

    raw_port = os.getenv("REDIS_PORT")
    if raw_port is not None:
        redis.port = parse_port_env("REDIS_PORT", raw_port)

    raw_host_port = os.getenv("REDIS_HOST_PORT")
    if raw_host_port is not None:
        redis.container.host_port = parse_port_env(
            "REDIS_HOST_PORT",
            raw_host_port,
        )

    raw_db = os.getenv("REDIS_DB")
    if raw_db is None:
        return

    database = parse_int_env("REDIS_DB", raw_db)
    if database < 0:
        raise ValueError("REDIS_DB must be greater than or equal to 0")

    redis.database = database


__all__ = [
    "apply_redis_env_overrides",
]
