"""pgAdmin config hook helpers."""

from __future__ import annotations

import os
from typing import Any


def apply_pgadmin_env_overrides(config: Any) -> None:
    """Apply pgAdmin runtime overrides from environment variables.

    Reads: PGADMIN_DEFAULT_EMAIL, PGADMIN_DEFAULT_PASSWORD.
    """
    pgadmin = config.pgadmin

    email = os.getenv("PGADMIN_DEFAULT_EMAIL")
    if email is not None:
        pgadmin.email = email

    password = os.getenv("PGADMIN_DEFAULT_PASSWORD")
    if password is not None:
        pgadmin.password = password


__all__ = [
    "apply_pgadmin_env_overrides",
]
