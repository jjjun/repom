"""SQLite configuration models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from repom.exec_env import normalize_exec_env

if TYPE_CHECKING:
    from repom.config import RepomConfig

# Path separators, ``:`` (a Windows drive prefix, and ``file:`` URIs), ``?`` and
# ``#`` (URL query/fragment delimiters), and ASCII/C1 control characters.
_UNSAFE_DB_FILE_NAME_PATTERN = re.compile(r"[/\\:?#\x00-\x1f\x7f-\x9f]")


def validate_sqlite_db_file_name(value: str, *, field_name: str) -> str:
    """Reject a SQLite file name that could leave the database directory.

    The name is joined onto ``db_path`` and rendered into a database URL, so it
    must not contain path separators, ``..``, ``:``, ``?``, ``#`` or control
    characters (including NUL). ``:`` covers a Windows drive prefix such as
    ``C:``, which pathlib would read as a drive and join to a path outside
    ``db_path``. Spaces and non-ASCII characters are allowed.
    """
    if not value or ".." in value or _UNSAFE_DB_FILE_NAME_PATTERN.search(value):
        raise ValueError(
            f"{field_name} must be a plain file name without path separators, "
            "'..', ':', '?', '#' or control characters"
        )
    return value


@dataclass
class SqliteConfig:
    """SQLite database settings."""

    db_path: Optional[str] = field(default=None)
    use_in_memory_for_tests: bool = field(default=True)
    _db_file: Optional[str] = field(default=None, init=False, repr=False)
    _config: Optional["RepomConfig"] = field(default=None, init=False, repr=False)

    def bind(self, config: "RepomConfig"):
        """Bind parent config for computed properties."""
        self._config = config

    def get_default_db_file(self, exec_env: str) -> str:
        """Get default SQLite DB file name by environment."""
        prefix = self._config.db_name if self._config else "db"
        validate_sqlite_db_file_name(prefix, field_name="db_name")
        normalized = normalize_exec_env(exec_env)

        if normalized == "test":
            return f"{prefix}_{normalized}.sqlite3"

        if normalized == "prod":
            return f"{prefix}.sqlite3"

        return f"{prefix}_dev.sqlite3"

    @property
    def db_file(self) -> Optional[str]:
        """Database file name, automatically calculated from bound config."""
        if self._db_file is not None:
            return self._db_file

        if not self._config:
            return None
        return self.get_default_db_file(self._config.exec_env)

    @db_file.setter
    def db_file(self, value: Optional[str]):
        # An empty value keeps selecting no file (db_url is None), as before.
        if value:
            validate_sqlite_db_file_name(value, field_name="sqlite.db_file")
        self._db_file = value

    @property
    def db_file_path(self) -> Optional[str]:
        """Return the full database file path."""
        if not self._config:
            return None
        db_path = self.db_path if self.db_path else self._config.data_path
        if not db_path:
            return None
        db_file = self.db_file
        if not db_file:
            return None
        return str(Path(db_path) / db_file)


__all__ = ["SqliteConfig", "validate_sqlite_db_file_name"]
