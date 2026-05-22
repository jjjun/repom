"""Redis config hook helpers."""

from __future__ import annotations

import os
from typing import Any


def apply_redis_env_overrides(config: Any) -> None:
    """Apply Redis runtime overrides from environment variables.

    Reads: REDIS_PORT.
    """
    redis = getattr(config, "redis", None)
    if redis is None:
        return

    raw_port = os.getenv("REDIS_PORT")
    if raw_port is None:
        return

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("REDIS_PORT must be an integer") from exc

    if not (0 < port < 65536):
        raise ValueError("REDIS_PORT must be between 1 and 65535")

    redis.port = port


__all__ = [
    "apply_redis_env_overrides",
]
