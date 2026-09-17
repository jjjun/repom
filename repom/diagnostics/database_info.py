"""Database information collection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession

import repom.config as config_module
from repom.database import safe_db_url


@dataclass
class DatabaseInfo:
    """Runtime database information."""

    backend: str
    target: str
    size_bytes: int | None
    size_text: str
    status: str
    error: str = ""


def format_size(size_bytes: int | None, *, unit: str = "auto") -> str:
    """Format a byte count for display.

    Args:
        size_bytes: Size in bytes. ``None`` is displayed as ``N/A``.
        unit: ``auto`` for human-readable units, or ``mb`` for fixed MB output.
    """
    if size_bytes is None:
        return "N/A"

    if unit == "mb":
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    if unit != "auto":
        raise ValueError("unit must be 'auto' or 'mb'")

    if size_bytes < 1024:
        return f"{size_bytes} B"

    units = ["KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for current_unit in units:
        size /= 1024
        if size < 1024 or current_unit == units[-1]:
            return f"{size:.2f} {current_unit}"
    return f"{size_bytes} B"


def resolve_sqlite_db_path(db_url: str, root_path: str | Path) -> Path | None:
    """Resolve a SQLite URL to a local file path."""
    try:
        url = make_url(db_url)
    except Exception:
        return None

    if url.get_backend_name() != "sqlite":
        return None

    database = url.database
    if not database or database == ":memory:" or database.startswith("file::memory:"):
        return None

    candidate = Path(database)
    if candidate.is_absolute():
        return candidate
    return Path(root_path) / candidate


def _database_target(config_obj: Any) -> str:
    return str(getattr(config_obj, "postgres_db", "") or config_obj.db_name)


def _get_config() -> Any:
    return config_module.config


@contextmanager
def short_lived_postgres_engine(
    config_obj: Any, *, connect_timeout: int = 3
) -> Iterator[Engine]:
    """Create a short-lived PostgreSQL engine for connectivity probes.

    Uses ``config_obj.engine_kwargs`` so consumer overrides (application_name,
    connect_args, etc.) still apply, but pins ``connect_args.connect_timeout``
    to a short value so a probe against an unreachable host fails quickly
    instead of waiting on the configured production timeout. The engine is
    always disposed, even when the connection attempt raises.
    """
    engine_kwargs = dict(config_obj.engine_kwargs)
    connect_args = dict(engine_kwargs.get("connect_args") or {})
    connect_args["connect_timeout"] = connect_timeout
    engine_kwargs["connect_args"] = connect_args

    engine = create_engine(config_obj.db_url, **engine_kwargs)
    try:
        yield engine
    finally:
        engine.dispose()


def _skipped_postgres_info(target: str) -> DatabaseInfo:
    return DatabaseInfo(
        backend="postgres",
        target=target,
        size_bytes=None,
        size_text="N/A (skipped)",
        status="ok",
    )


def _unavailable_postgres_info(target: str, error: str) -> DatabaseInfo:
    return DatabaseInfo(
        backend="postgres",
        target=target,
        size_bytes=None,
        size_text="N/A",
        status="unavailable",
        error=error,
    )


def _unsupported_backend_info(config_obj: Any) -> DatabaseInfo:
    return DatabaseInfo(
        backend=str(config_obj.db_type),
        target=safe_db_url(str(config_obj.db_url)),
        size_bytes=None,
        size_text="N/A",
        status="unsupported",
        error=f"Unsupported database backend: {config_obj.db_type}",
    )


def collect_database_info_sync(
    *,
    include_database_size: bool = True,
) -> DatabaseInfo:
    """Collect database information using synchronous SQLAlchemy APIs."""
    config = _get_config()
    db_url = str(config.db_url)

    if config.db_type == "sqlite":
        db_path = resolve_sqlite_db_path(db_url, config.root_path)
        if db_path is None:
            return DatabaseInfo(
                backend="sqlite",
                target=":memory:",
                size_bytes=None,
                size_text="N/A (in-memory)",
                status="ok",
            )

        exists = db_path.exists()
        size_bytes = db_path.stat().st_size if exists else 0
        return DatabaseInfo(
            backend="sqlite",
            target=str(db_path),
            size_bytes=size_bytes,
            size_text=format_size(size_bytes),
            status="ok" if exists else "unavailable",
            error="" if exists else "SQLite database file not found",
        )

    if config.db_type == "postgres":
        target = _database_target(config)
        if not include_database_size:
            return _skipped_postgres_info(target)

        try:
            with short_lived_postgres_engine(config) as engine:
                with engine.connect() as conn:
                    size_bytes = int(
                        conn.execute(
                            text("SELECT pg_database_size(current_database())")
                        ).scalar_one()
                    )

            return DatabaseInfo(
                backend="postgres",
                target=target,
                size_bytes=size_bytes,
                size_text=format_size(size_bytes),
                status="ok",
            )
        except Exception as exc:
            return _unavailable_postgres_info(target, str(exc))

    return _unsupported_backend_info(config)


async def collect_database_info_async(
    session: AsyncSession | None = None,
    *,
    include_database_size: bool = True,
) -> DatabaseInfo:
    """Collect database information using an optional async session."""
    config = _get_config()
    if config.db_type == "sqlite":
        return collect_database_info_sync(include_database_size=include_database_size)

    if config.db_type == "postgres":
        target = _database_target(config)
        if not include_database_size:
            return _skipped_postgres_info(target)
        if session is None:
            return _unavailable_postgres_info(target, "Async session is not available")

        try:
            result = await session.execute(
                text("SELECT pg_database_size(current_database())")
            )
            size_bytes = int(result.scalar_one())
            return DatabaseInfo(
                backend="postgres",
                target=target,
                size_bytes=size_bytes,
                size_text=format_size(size_bytes),
                status="ok",
            )
        except Exception as exc:
            return _unavailable_postgres_info(target, str(exc))

    return _unsupported_backend_info(config)
