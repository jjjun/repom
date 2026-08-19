from functools import lru_cache

from sqlalchemy import ARRAY, JSON, String, inspect
from sqlalchemy.types import TypeDecorator

from repom.exceptions import NulByteError


def validate_no_nul_byte(
    value: str, column_name: str, key_path: str | None = None
) -> None:
    """Raise NulByteError when a string contains a NUL byte."""
    character_offset = value.find('\0')
    if character_offset != -1:
        offset = len(value[:character_offset].encode('utf-8'))
        raise NulByteError(column_name, offset, key_path)


def _unwrap_type(column_type):
    while isinstance(column_type, TypeDecorator):
        column_type = column_type.impl
    return column_type


def _validation_mode(column) -> str | None:
    if isinstance(column.type, String):
        return 'string'

    column_type = _unwrap_type(column.type)
    if isinstance(column_type, String):
        return 'document'
    if isinstance(column_type, JSON):
        return 'document'
    if isinstance(column_type, ARRAY) and isinstance(
        _unwrap_type(column_type.item_type), String
    ):
        return 'document'
    return None


@lru_cache(maxsize=None)
def _string_columns(mapper) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (column.key, f"{column.table.fullname}.{column.name}", mode)
        for column in mapper.columns
        if (mode := _validation_mode(column)) is not None
    )


def _child_path(path: str | None, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path or ''}[{key}]"
    return f"{path}.{key}" if path else key


def _validate_document_no_nul_bytes(value, column_name: str, path: str | None = None) -> None:
    if isinstance(value, str):
        validate_no_nul_byte(value, column_name, path or '$')
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                key_path = _child_path(path, key)
                validate_no_nul_byte(key, column_name, key_path)
            else:
                key_path = _child_path(path, str(key))
            _validate_document_no_nul_bytes(item, column_name, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_document_no_nul_bytes(item, column_name, _child_path(path, index))


def validate_model_no_nul_bytes(target) -> None:
    """Validate cached scalar and document columns on a mapped model instance."""
    instance_state = inspect(target)
    for key, column_name, mode in _string_columns(instance_state.mapper):
        if key not in instance_state.dict:
            continue
        if instance_state.persistent and not instance_state.attrs[key].history.has_changes():
            continue
        value = instance_state.dict[key]
        if mode == 'string' and isinstance(value, str):
            validate_no_nul_byte(value, column_name)
        elif mode == 'document':
            _validate_document_no_nul_bytes(value, column_name)


def validate_values_no_nul_bytes(model, values: dict) -> None:
    """Validate scalar and document values for a Core update of a mapped model."""
    for key, column_name, mode in _string_columns(inspect(model).mapper):
        value = values.get(key)
        if mode == 'string' and isinstance(value, str):
            validate_no_nul_byte(value, column_name)
        elif mode == 'document':
            _validate_document_no_nul_bytes(value, column_name)
