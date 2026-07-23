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

from repom.custom_types.JSONEncoded import JSONEncoded


class Event(BaseModel):
    __tablename__ = "events"

    payload: Mapped[dict] = mapped_column(JSONEncoded)
```

`JSONEncoded` remains for compatibility; new models should normally prefer
SQLAlchemy's native `JSON` type. Custom type behavior can affect migration
output and cross-database compatibility, so applications should add
round-trip tests for every database engine they support.

## Related documentation

- [BaseModelAuto guide](base_model_auto_guide.md)
- [Soft-delete guide](soft_delete_guide.md)
- [Model guide index](README.md)
