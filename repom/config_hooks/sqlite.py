"""SQLite config hook helpers."""

from __future__ import annotations

import os
from typing import Any

from repom.config_hooks._parsing import TRUE_VALUES, parse_bool_env


def apply_sqlite_env_overrides(config: Any) -> None:
    """Apply SQLite runtime overrides from environment variables.

    Reads: SQLITE_DB_PATH, SQLITE_DB_FILE, SQLITE_USE_IN_MEMORY_FOR_TESTS,
    SQLITE_USE_FILE_DB.
    """
    sqlite = getattr(config, "sqlite", None)
    if sqlite is None:
        return

    db_path = os.getenv("SQLITE_DB_PATH")
    if db_path is not None:
        sqlite.db_path = db_path

    db_file = os.getenv("SQLITE_DB_FILE")
    if db_file is not None:
        sqlite.db_file = db_file

    raw_use_file_db = os.getenv("SQLITE_USE_FILE_DB")
    if raw_use_file_db is not None and raw_use_file_db.strip().lower() in TRUE_VALUES:
        sqlite.use_in_memory_for_tests = False

    raw_use_in_memory = os.getenv("SQLITE_USE_IN_MEMORY_FOR_TESTS")
    if raw_use_in_memory is not None:
        sqlite.use_in_memory_for_tests = parse_bool_env(
            "SQLITE_USE_IN_MEMORY_FOR_TESTS",
            raw_use_in_memory,
        )


__all__ = [
    "apply_sqlite_env_overrides",
]
