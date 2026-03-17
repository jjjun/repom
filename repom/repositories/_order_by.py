"""Repository-backed order_by introspection and FastAPI helpers."""

from __future__ import annotations

import inspect
from enum import Enum
from typing import Optional, Type, get_args

from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm.exc import UnmappedClassError


class VirtualColumnError(ValueError):
    """Raised when a virtual order_by column requires manual query handling."""

    def __init__(self, column_name: str, direction: str):
        self.column_name = column_name
        self.direction = direction
        super().__init__(
            f"'{column_name}' is a virtual order_by column. "
            "Handle sorting manually in a custom repository method."
        )


def get_repository_model_class(repository_class: type) -> Type:
    """Resolve the SQLAlchemy model class from a repository class."""
    if hasattr(repository_class, "__orig_bases__"):
        for base in repository_class.__orig_bases__:
            args = get_args(base)
            if args:
                return args[0]

    raise TypeError(
        f"Could not extract model from repository class {repository_class.__name__}"
    )


def get_order_by_columns(repository_class: type) -> list[str]:
    """Return orderable columns that exist on the repository model."""
    model_class = get_repository_model_class(repository_class)
    allowed_columns = list(getattr(repository_class, "allowed_order_columns", []))
    virtual_columns = list(getattr(repository_class, "virtual_order_columns", []))

    invalid_virtual_columns = [
        column for column in virtual_columns if column not in allowed_columns
    ]
    if invalid_virtual_columns:
        invalid_columns_str = ", ".join(sorted(invalid_virtual_columns))
        raise ValueError(
            "virtual_order_columns must also be present in allowed_order_columns: "
            f"{invalid_columns_str}"
        )

    try:
        mapper = sa_inspect(model_class)
    except UnmappedClassError as exc:
        raise TypeError(f"Model {model_class.__name__} is not a mapped class") from exc

    model_columns = set(mapper.columns.keys())
    virtual_columns_set = set(virtual_columns)
    return [
        column
        for column in allowed_columns
        if column in model_columns or column in virtual_columns_set
    ]


def normalize_order_by_value(order_by_value: str) -> tuple[str, str]:
    """Normalize a canonical ``order_by`` string into column and direction."""
    if not isinstance(order_by_value, str):
        raise TypeError("order_by value must be a string")

    if ":" not in order_by_value:
        raise ValueError(
            "order_by must use canonical format 'column:asc' or 'column:desc'"
        )

    column_name, direction = order_by_value.split(":", 1)
    column_name = column_name.strip()
    direction = direction.strip().lower()

    if not column_name:
        raise ValueError("order_by column must not be empty")

    if direction not in {"asc", "desc"}:
        raise ValueError(f"Direction must be 'asc' or 'desc', got '{direction}'")

    return column_name, direction


def get_order_by_values(repository_class: type) -> list[str]:
    """Return canonical ``order_by`` values for OpenAPI exposure."""
    values: list[str] = []
    for column in get_order_by_columns(repository_class):
        values.append(f"{column}:asc")
        values.append(f"{column}:desc")
    return values


def get_order_by_default_value(repository_class: type) -> str | None:
    """Return a canonical default ``order_by`` value when it can be exposed."""
    default_order_by = getattr(repository_class, "default_order_by", None)

    if default_order_by is None:
        return None

    if not isinstance(default_order_by, str):
        return None

    column_name, direction = normalize_order_by_value(default_order_by)
    allowed_values = set(get_order_by_values(repository_class))
    canonical_value = f"{column_name}:{direction}"

    if canonical_value not in allowed_values:
        raise ValueError(
            f"default_order_by '{default_order_by}' is not valid for "
            f"{repository_class.__name__}"
        )

    return canonical_value


def build_order_by_query_depends(
    repository_class: type,
    *,
    description: str | None = None,
):
    """Build a FastAPI dependency that exposes canonical order_by enum values."""
    try:
        from fastapi import Query
    except ImportError as exc:
        raise ImportError(
            "FastAPI is required to use build_order_by_query_depends(). "
            "Install it in the consuming project."
        ) from exc

    allowed_values = get_order_by_values(repository_class)
    default_value = get_order_by_default_value(repository_class)

    enum_name = f"{repository_class.__name__}OrderBy"
    members = {
        value.replace(":", "_").replace("-", "_").upper(): value
        for value in allowed_values
    }
    order_by_enum = Enum(enum_name, members, type=str)

    query_description = description or (
        f"Sort order for {repository_class.__name__}. "
        "Use canonical form 'column:asc' or 'column:desc'."
    )

    default_enum = order_by_enum(default_value) if default_value is not None else None
    query_param = Query(default_enum, description=query_description)

    def query_depends(**kwargs):
        order_by = kwargs.get("order_by")
        if order_by is None:
            return {"order_by": None}
        return {"order_by": order_by.value}

    query_depends.__name__ = f"{repository_class.__name__}_order_by_depends"
    query_depends.__annotations__ = {"order_by": Optional[order_by_enum]}
    query_depends.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter(
                name="order_by",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=query_param,
                annotation=Optional[order_by_enum],
            )
        ],
        return_annotation=dict,
    )

    return query_depends
