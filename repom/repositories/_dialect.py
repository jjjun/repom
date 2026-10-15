"""Dialect-specific SQL statement helpers."""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Dialect, Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute

from repom.custom_types.AutoDateTime import AutoDateTime
from repom.nul_bytes import validate_values_no_nul_bytes


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


def build_upsert(
    target: str | Dialect | Engine | Connection | Session | AsyncSession,
    model: Any,
    values: dict | Sequence[dict],
    *,
    conflict_columns: Sequence[str | InstrumentedAttribute],
    update_columns: Sequence[str | InstrumentedAttribute] | None = None,
    index_where: Any = None,
    where: Any = None,
) -> Any:
    """Build an INSERT ... ON CONFLICT DO UPDATE statement for a mapped model."""
    mapper = inspect(model)
    rows, input_keys = _prepare_insert_values(model, values)
    conflict_keys = _resolve_column_keys(
        model, conflict_columns, argument_name='conflict_columns'
    )
    if not conflict_keys:
        raise ValueError('conflict_columns must contain at least one mapped column.')
    _reject_duplicate_conflict_keys(rows, conflict_keys)
    conflict_key_set = set(conflict_keys)

    primary_key_keys = {
        prop.key
        for prop in mapper.column_attrs
        if any(column.primary_key for column in prop.columns)
    }
    if update_columns is None:
        resolved_update_keys = [
            key
            for key in input_keys
            if key not in conflict_key_set
            and key not in primary_key_keys
            and key not in {'created_at', 'updated_at'}
        ]
    else:
        resolved_update_keys = _resolve_column_keys(
            model, update_columns, argument_name='update_columns', error_type=ValueError
        )
        if not set(resolved_update_keys).issubset(set(input_keys)):
            raise ValueError('update_columns must be a subset of the values keys.')
        resolved_update_key_set = set(resolved_update_keys)
        if resolved_update_key_set & conflict_key_set:
            raise ValueError('update_columns must not include a conflict column.')
        if resolved_update_key_set & primary_key_keys:
            raise ValueError('update_columns must not include a primary key column.')
        if 'created_at' in resolved_update_key_set:
            raise ValueError('created_at is never updated on conflict.')

    if not resolved_update_keys:
        raise ValueError(
            'upsert() has no columns to update; use insert_ignore() instead.'
        )

    update_at_is_auto = _has_auto_datetime_column(mapper, 'updated_at')
    if update_at_is_auto and 'updated_at' not in resolved_update_keys:
        resolved_update_keys.append('updated_at')

    statement = insert_for_dialect(target, model).values(rows)
    set_values = {key: statement.excluded[key] for key in resolved_update_keys}
    return statement.on_conflict_do_update(
        index_elements=[getattr(model, key) for key in conflict_keys],
        index_where=index_where,
        set_=set_values,
        where=where,
    )


def build_insert_ignore(
    target: str | Dialect | Engine | Connection | Session | AsyncSession,
    model: Any,
    values: dict | Sequence[dict],
    *,
    conflict_columns: Sequence[str | InstrumentedAttribute],
    index_where: Any = None,
) -> Any:
    """Build an INSERT ... ON CONFLICT DO NOTHING statement for a mapped model."""
    rows, _ = _prepare_insert_values(model, values)
    conflict_keys = _resolve_column_keys(
        model, conflict_columns, argument_name='conflict_columns'
    )
    if not conflict_keys:
        raise ValueError('conflict_columns must contain at least one mapped column.')
    _reject_duplicate_conflict_keys(rows, conflict_keys)

    statement = insert_for_dialect(target, model).values(rows)
    return statement.on_conflict_do_nothing(
        index_elements=[getattr(model, key) for key in conflict_keys],
        index_where=index_where,
    )


def _prepare_insert_values(model: Any, values: dict | Sequence[dict]) -> tuple[list[dict], list[str]]:
    if isinstance(values, dict):
        rows = [dict(values)]
    elif isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
        if not all(isinstance(row, dict) for row in values):
            raise TypeError('values must be a dict or a sequence of dicts.')
        rows = [dict(row) for row in values]
    else:
        raise TypeError('values must be a dict or a sequence of dicts.')

    if not rows:
        raise ValueError('values must contain at least one row.')

    mapper = inspect(model)
    input_keys = list(rows[0])
    input_key_set = set(input_keys)
    for row in rows:
        if set(row) != input_key_set:
            raise ValueError('Every values row must have the same set of keys.')
        for key in row:
            if not isinstance(key, str) or key not in mapper.column_attrs:
                raise TypeError(f'{key!r} is not a mapped column attribute of {model.__name__}.')

    timestamp_columns = {
        key
        for key in ('created_at', 'updated_at')
        if _has_auto_datetime_column(mapper, key)
    }
    if timestamp_columns:
        now = datetime.now(timezone.utc)
        for row in rows:
            for key in timestamp_columns:
                row.setdefault(key, now)

    for row in rows:
        validate_values_no_nul_bytes(model, row)

    return rows, input_keys


def _resolve_column_keys(
    model: Any,
    columns: Sequence[str | InstrumentedAttribute],
    *,
    argument_name: str,
    error_type: type[Exception] = TypeError,
) -> list[str]:
    if isinstance(columns, (str, bytes, bytearray)) or not isinstance(columns, Sequence):
        raise error_type(f'{argument_name} must be a sequence of mapped column attributes.')

    mapper = inspect(model)
    resolved_keys: list[str] = []
    for column in columns:
        if isinstance(column, str):
            key = column
        elif isinstance(column, InstrumentedAttribute):
            key = column.key
            if key not in mapper.column_attrs or column.property is not mapper.column_attrs[key]:
                raise error_type(f'{column!r} is not a mapped column attribute of {model.__name__}.')
        else:
            raise error_type(f'{column!r} is not a mapped column attribute of {model.__name__}.')

        if key not in mapper.column_attrs:
            raise error_type(f'{key!r} is not a mapped column attribute of {model.__name__}.')
        if key in resolved_keys:
            raise ValueError(f'{argument_name} must not contain duplicate columns.')
        resolved_keys.append(key)

    return resolved_keys


def _has_auto_datetime_column(mapper: Any, key: str) -> bool:
    prop = mapper.column_attrs.get(key)
    return prop is not None and any(isinstance(column.type, AutoDateTime) for column in prop.columns)


def _reject_duplicate_conflict_keys(rows: list[dict], conflict_keys: list[str]) -> None:
    seen_keys: set[tuple[Any, ...]] = set()
    seen_keys_list: list[tuple[Any, ...]] = []
    for row in rows:
        if not all(key in row for key in conflict_keys):
            continue
        conflict_key = tuple(row[key] for key in conflict_keys)
        try:
            if conflict_key in seen_keys:
                raise ValueError('values contains duplicate conflict-column values.')
            seen_keys.add(conflict_key)
        except TypeError:
            if conflict_key in seen_keys_list:
                raise ValueError('values contains duplicate conflict-column values.')
        seen_keys_list.append(conflict_key)
