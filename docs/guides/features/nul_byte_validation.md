# NUL byte validation

repom rejects values containing a NUL byte (`0x00`) in `String` and `Text`
columns before they reach the database. It also rejects NUL bytes in `JSON`,
`CustomJSON`, `ListJSON`, and `ARRAY(String)` values, including nested dict
keys and values. It raises `NulByteError`, which names the column and byte
offset; document errors also include the key path so applications can map the
error to a 4xx response.

The guard runs for inserts and updates of `BaseModel` subclasses in every
SQLAlchemy session. `BaseRepository.bulk_update` and
`AsyncBaseRepository.bulk_update` validate their Core update values as well.
On updates, unloaded and unchanged attributes are skipped to avoid loading
deferred columns solely for validation. In-place mutations to a dict or list
are not written or validated unless the column uses SQLAlchemy mutable tracking
(for example, `MutableDict`) or the application assigns a new value.

`JSONEncoded` is intentionally excluded. It stores JSON-encoded text, where a
NUL round-trips losslessly and cannot be used with server-side JSON extraction.
repom rejects values where a real NUL byte would reach the column, or where a
stored JSON escape would make the value unreadable through server-side
extraction; it does not reject values where the escape round-trips losslessly.

`StrEncodedArray` validates its encoded text value separately. Because its
bind processor has no mapped-column context, `NulByteError.column_name` is
`StrEncodedArray`. Its offset is into the comma-joined encoded string, not an
individual list element.

## Detecting existing PostgreSQL JSON values

For a `json` column that may contain values written before this validation was
added, use a non-pattern search to obtain a cheap superset of candidates:

```sql
SELECT id
FROM my_table
WHERE strpos(payload::text, chr(92) || 'u0000') > 0;
```

Confirm each candidate by casting it to `jsonb`; a failed cast identifies a
poisoned value, while a successful cast identifies an ordinary escaped sequence
such as prose discussing `\\u0000`:

```sql
SELECT payload::jsonb
FROM my_table
WHERE id = :id;
```

## Performance

On this repository's benchmark, a 1,000-row insert with scalar string values
averaged 45.3018 ms. The same insert with a payload containing 100 nested JSON
items averaged 352.1811 ms, about 7.8 times as long and roughly 307 microseconds
of additional guard cost per row. Consumers storing large crawled JSON payloads
should account for this document-walk cost.
