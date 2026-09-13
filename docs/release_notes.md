# Release notes

## Unreleased

- BREAKING: `bulk_update()` and `bulk_delete()` now raise `ValueError` when the
  resolved filter list is empty (`bulk_delete()` with neither `filter_by` nor
  `ids`, or `bulk_update(..., filter_by={})`). Pass `allow_unfiltered=True` to
  keep the previous whole-table behaviour. Filter keys and the `ids` sequence
  are now resolved through the SQLAlchemy mapper, so relationship names, dunder
  attributes and SQL expressions are rejected instead of compiling to `WHERE true`.
- BREAKING: Removed `JSONEncoded` and `StrEncodedArray`. Use `CustomJSON` for
  object-like JSON values and `ListJSON` for list values. If a historical
  migration imports either removed type solely for a `TEXT` column in
  `op.create_table`, replace it with `sa.TEXT()`; this emits identical DDL and
  lets fresh database bootstraps proceed.
- NUL bytes in `String` and `Text` columns now raise `NulByteError` on every
  supported dialect, including SQLite. SQLite-backed consumers that previously
  stored NUL bytes must reject or sanitize those values before persistence.
- NUL bytes in `JSON`, `CustomJSON`, `ListJSON`, and `ARRAY(String)` values now
  raise `NulByteError`, including nested document keys and values. To find
  existing poisoned PostgreSQL `json` rows, use
  `strpos(payload::text, chr(92) || 'u0000') > 0` only as a cheap
  superset pre-filter, then confirm each candidate by casting the stored value
  to `jsonb`; the cast is authoritative, while the pre-filter can match ordinary
  prose containing the escape sequence.
- NUL bytes in `TypeDecorator` columns that resolve to a `String` family type,
  including `JSONEncoded`, now raise `NulByteError` with document key paths.
  For existing JSON-over-TEXT values, use
  `strpos(payload, chr(92) || 'u0000') > 0` as a candidate pre-filter, then
  parse each candidate with `json.loads` and recursively check for a real NUL
  byte. The pre-filter also matches ordinary prose containing the escape
  sequence, so parsing is required to confirm a poisoned value.
- BREAKING: `field_to_column` string fields now match exactly (`==`) instead
  of an unescaped `LIKE` substring match. Consumers that relied on the
  implicit substring search must wrap the column with `contains_column()` or
  `prefix_column()`; both escape `%` and `_` and reject values longer than
  `max_length` (default 256).
- BREAKING: `ListJSON` now stores a real JSON array instead of a
  double-encoded JSON string. Reads remain compatible with both formats, but
  `listjson_filter()` and the empty-list filter (`column == []`) only match
  rows written in the new format, so rows written by earlier versions will
  not be found until they are rewritten. To rewrite existing rows:
  - SQLite: `UPDATE t SET col = json(json_extract(col, '$')) WHERE json_type(col) = 'text'`
  - PostgreSQL `json`: `UPDATE t SET col = (col #>> '{}')::json WHERE json_typeof(col) = 'string'`
