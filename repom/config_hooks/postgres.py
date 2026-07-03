"""PostgreSQL config hook helpers."""

from __future__ import annotations

import os
from typing import Any

from repom.config_hooks._parsing import parse_port_env


def apply_postgres_env_overrides(config: Any) -> None:
    """Apply PostgreSQL runtime overrides from environment variables.

    Reads: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_HOST_PORT.
    """
    postgres = config.postgres

    user = os.getenv("POSTGRES_USER")
    if user is not None:
        postgres.user = user

    password = os.getenv("POSTGRES_PASSWORD")
    if password is not None:
        postgres.password = password

    host = os.getenv("POSTGRES_HOST")
    if host is not None:
        postgres.host = host

    raw_port = os.getenv("POSTGRES_PORT")
    if raw_port is not None:
        postgres.port = parse_port_env("POSTGRES_PORT", raw_port)

    raw_host_port = os.getenv("POSTGRES_HOST_PORT")
    if raw_host_port is not None:
        postgres.container.host_port = parse_port_env(
            "POSTGRES_HOST_PORT",
            raw_host_port,
        )


__all__ = [
    "apply_postgres_env_overrides",
]
