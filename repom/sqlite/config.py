"""SQLite configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from repom.config import RepomConfig


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
        if exec_env in ("test", "dev"):
            return f"{prefix}_{exec_env}.sqlite3"
        return f"{prefix}.sqlite3"

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


__all__ = ["SqliteConfig"]
