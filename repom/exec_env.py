"""Execution environment normalization helpers."""

from __future__ import annotations

import logging
from threading import Lock


_logger = logging.getLogger(__name__)
_warned_unknown_exec_envs: set[str] = set()
_warning_lock = Lock()


def is_prod_exec_env(value: str) -> bool:
    """Return whether *value* names the production execution environment."""
    return value.strip().lower() in {"prod", "production"}


def normalize_exec_env(value: str) -> str:
    """Return a canonical environment name, using dev defaults for unknown values."""
    normalized = value.strip().lower()
    if normalized in {"dev", "test"}:
        return normalized
    if is_prod_exec_env(normalized):
        return "prod"

    with _warning_lock:
        if value not in _warned_unknown_exec_envs:
            _warned_unknown_exec_envs.add(value)
            _logger.warning(
                "Unknown EXEC_ENV=%r; using dev database defaults for PostgreSQL "
                "and SQLite.",
                value,
            )
    return "dev"
