"""Dialect-specific SQL statement helpers."""

from typing import Any

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Dialect, Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


def insert_for_dialect(
    target: str | Dialect | Engine | Connection | Session | AsyncSession,
    table_or_model: Any,
) -> Any:
    """Build an INSERT statement for PostgreSQL or SQLite.

    ``target`` can be a dialect name, dialect, engine, connection, or session.
    Sessions are resolved through ``get_bind()`` so callers can use this helper
    when they only have a session available.
    """
    if isinstance(target, str):
        dialect_name = target
    elif isinstance(target, Dialect):
        dialect_name = target.name
    elif isinstance(target, (Session, AsyncSession)):
        dialect_name = target.get_bind().dialect.name
    else:
        dialect_name = target.dialect.name

    if dialect_name == 'postgresql':
        return postgresql_insert(table_or_model)
    if dialect_name == 'sqlite':
        return sqlite_insert(table_or_model)

    raise NotImplementedError(
        f"INSERT with ON CONFLICT is not supported for dialect {dialect_name!r}"
    )
