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

The flags can also be declared as class attributes. Subclasses inherit those
values, and class parameters take precedence when both forms are supplied. An
intermediate abstract class without `__tablename__` receives no generated
columns; its concrete subclasses apply the inherited flags when their table
is mapped:

```python
class CompositeModel(BaseModel):
    __abstract__ = True
    use_id = False


class ExternalMembership(CompositeModel):
    __tablename__ = "external_memberships"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
```

UUID values are assigned during construction. Timestamp columns have no Python
or server defaults. On INSERT, `AutoDateTime` supplies their values while
SQLAlchemy binds the INSERT, so the model attributes are still `None` after a
flush; call `session.refresh(instance)` to load the stored timestamps. On
UPDATE, the `updated_at` event sets that attribute before the flush. `repo.save()`
refreshes only when it uses an internal session.

## Custom SQLAlchemy types

Reusable types live in [`repom/custom_types`](../../../repom/custom_types).
They include date/time conversion helpers and JSON-backed values. Import a
concrete type from its module and inspect its implementation and tests before
selecting it for a persistent schema:

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

`AutoDateTime` normalizes every value to UTC before it reaches the DBAPI: a
timezone-aware value is converted with `astimezone(timezone.utc)`, and a naive
value is treated as already UTC and only gets `tzinfo` attached. This keeps
the stored instant correct even on backends that cannot retain a UTC offset
(SQLite stores the wall-clock component only). On read, a naive value coming
back from such a backend is labelled `timezone.utc`; a value that already
carries tzinfo (for example PostgreSQL `timestamptz`) is converted to UTC.

`UTCDateTime` uses the same bind and result normalization while preserving
`None`, so it is suitable for nullable datetime columns that should always
read back as UTC-aware values:

```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

from repom.custom_types import UTCDateTime

started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
```

`ISO8601DateTime` (`impl = DateTime`) stores a `datetime` using the dialect's
native `DateTime` column type; it does not emit an ISO 8601 string. Binding
passes a `datetime` value through unchanged (`None` stays `None`; any other
type raises `ValueError`), and reading passes the dialect's `datetime` result
through unchanged, only parsing with `datetime.fromisoformat()` when the
driver hands back a `str`. `ISO8601DateTimeStr` (`impl = String`) is the
distinct string-storage type: it serializes a `datetime` with `.isoformat()`
on bind and parses it back with `datetime.fromisoformat()` on read, so the
column stores an ISO 8601 string. Choose `ISO8601DateTimeStr` when the schema
needs a text column; choose `ISO8601DateTime` (or `AutoDateTime`) for a native
datetime column.

`ListJSON` ships a `listjson_filter(model_column, values)` helper that builds
filter conditions for "column contains each of these values" queries. Each
distinct requested value becomes a correlated `EXISTS` against the
`json_each` expansion, rather than a table-valued join added to the outer
query, so a repeated array element or several requested values never
multiply the outer model rows, inflate `count()`, or push a matching row
past a `limit`/`offset` page. For element matching, it uses
`json_array_elements_text()` on PostgreSQL and `json_each()` on SQLite.
For an empty-list match, both dialects use `json_array_length(...) == 0`.
Callers do not need to branch on dialect themselves.

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
