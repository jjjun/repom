# System columns and custom types

`BaseModel` lets an application opt in to common primary-key and timestamp
columns. The defaults are deliberately small so consuming applications can
choose their own schema.

## System-column options

Configure options as class parameters:

```python
from repom import BaseModel


class Article(
    BaseModel,
    use_created_at=True,
    use_updated_at=True,
):
    __tablename__ = "articles"
```

| Option | Default | Effect |
| --- | --- | --- |
| `use_id` | `True` | Adds an integer `id` primary key. |
| `use_uuid` | `False` | Adds a string UUID primary key and disables the default integer key. |
| `use_created_at` | `False` | Adds a creation timestamp. |
| `use_updated_at` | `False` | Adds an update timestamp maintained by a SQLAlchemy event. |

Setting both `use_id` and `use_uuid` explicitly to `True` is invalid. For a
composite or application-defined key, disable the generated key and declare
the mapped primary-key columns yourself:

```python
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseModel


class Membership(BaseModel, use_id=False):
    __tablename__ = "memberships"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
```

UUID values are assigned during construction. Timestamp values are populated
when SQLAlchemy inserts or updates the row, so flush before relying on their
final values.

## Custom SQLAlchemy types

Reusable types live in [`repom/custom_types`](../../../repom/custom_types).
They include date/time conversion helpers, JSON-backed values, and encoded
array helpers. Import a concrete type from its module and inspect its
implementation and tests before selecting it for a persistent schema:

```python
from sqlalchemy.orm import Mapped, mapped_column

from repom.custom_types.CustomJSON import CustomJSON


class Event(BaseModel):
    __tablename__ = "events"

    payload: Mapped[dict] = mapped_column(CustomJSON)
```

Use `CustomJSON` for object-like JSON values and `ListJSON` for list values.
Custom type behavior can affect migration output and cross-database
compatibility, so applications should add round-trip tests for every database
engine they support.

`ListJSON` ships a `listjson_filter(model_column, values)` helper that builds
filter conditions for "column contains each of these values" queries. It is
dialect-aware: PostgreSQL's `json_each()`/`json_each_text()` only accept JSON
objects and its `json` type has no equality operator, so on PostgreSQL the
element match compiles to `json_array_elements_text()` and the empty-list
match compiles to `json_array_length(...) == 0`. SQLite keeps using
`json_each()`, which already handles arrays and compares dynamically typed
values directly. Callers do not need to branch on dialect themselves.

## Mass-assignment and serialization allowlists

`update_from_dict()` requires an explicit allowlist. Pass `allowed_fields`, or
set the class attribute `updatable_fields`, or the call raises `ValueError`:

```python
class Profile(BaseModel):
    __tablename__ = "profiles"
    updatable_fields = {"display_name", "bio"}

    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str] = mapped_column(String(500))
    is_admin: Mapped[bool] = mapped_column(default=False)


profile.update_from_dict(request_json)  # only display_name / bio can change
```

Primary-key columns (resolved from the mapper, whatever their name),
`created_at`, `updated_at`, and `deleted_at` (when the model has it) are
excluded unconditionally, even if listed in `updatable_fields` or
`allowed_fields`. `exclude_fields` narrows the allowlist further for a single
call; it cannot widen it.

`to_dict()` still returns every column by default. Set `sensitive_fields` to
exclude columns such as password hashes from the output, and optionally
`serializable_fields` to return only an explicit subset:

```python
class Profile(BaseModel):
    __tablename__ = "profiles"
    sensitive_fields = {"password_hash"}
```

## Related documentation

- [Soft-delete guide](soft_delete_guide.md)
- [Model guide index](README.md)

FastAPI schema generation now lives in the consuming framework.
