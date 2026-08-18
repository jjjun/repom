from functools import lru_cache

from sqlalchemy import String, inspect

from repom.exceptions import NulByteError


def validate_no_nul_byte(value: str, column_name: str) -> None:
    """Raise NulByteError when a string contains a NUL byte."""
    character_offset = value.find('\0')
    if character_offset != -1:
        offset = len(value[:character_offset].encode('utf-8'))
        raise NulByteError(column_name, offset)


@lru_cache(maxsize=None)
def _string_columns(mapper) -> tuple[tuple[str, str], ...]:
    return tuple(
        (column.key, f"{column.table.fullname}.{column.name}")
        for column in mapper.columns
        if isinstance(column.type, String)
    )


def validate_model_no_nul_bytes(target) -> None:
    """Validate the cached String-family columns on a mapped model instance."""
    instance_state = inspect(target)
    for key, column_name in _string_columns(instance_state.mapper):
        if key not in instance_state.dict:
            continue
        if instance_state.persistent and not instance_state.attrs[key].history.has_changes():
            continue
        value = instance_state.dict[key]
        if isinstance(value, str):
            validate_no_nul_byte(value, column_name)


def validate_values_no_nul_bytes(model, values: dict) -> None:
    """Validate String-family values for a Core update of a mapped model."""
    for key, column_name in _string_columns(inspect(model).mapper):
        value = values.get(key)
        if isinstance(value, str):
            validate_no_nul_byte(value, column_name)
