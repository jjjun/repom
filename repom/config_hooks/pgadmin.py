"""pgAdmin config hook helpers."""

from __future__ import annotations

import os
from typing import Any

from repom.config_hooks._parsing import parse_port_env


def apply_pgadmin_env_overrides(config: Any) -> None:
    """Apply pgAdmin runtime overrides from environment variables.

    Reads: PGADMIN_DEFAULT_EMAIL, PGADMIN_DEFAULT_PASSWORD, PGADMIN_HOST_PORT.
    """
    pgadmin = config.pgadmin

    email = os.getenv("PGADMIN_DEFAULT_EMAIL")
    if email is not None:
        pgadmin.email = email

    password = os.getenv("PGADMIN_DEFAULT_PASSWORD")
    if password is not None:
        pgadmin.password = password

    raw_host_port = os.getenv("PGADMIN_HOST_PORT")
    if raw_host_port is not None:
        pgadmin.container.host_port = parse_port_env(
            "PGADMIN_HOST_PORT",
            raw_host_port,
        )


__all__ = [
    "apply_pgadmin_env_overrides",
]
