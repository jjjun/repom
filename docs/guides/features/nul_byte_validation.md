# NUL byte validation

repom rejects values containing a NUL byte (`0x00`) in every mapped column
whose type resolves to a `String` or `JSON` family type, including through
`TypeDecorator`s. This includes `CustomJSON`, `ListJSON`, and
`ARRAY(String)` values, including nested dict keys and values. It raises
`NulByteError`, which names the column and byte offset; document errors also
include the key path so applications can map the error to a 4xx response.

The guard runs for inserts and updates of `BaseModel` subclasses in every
SQLAlchemy session. `BaseRepository.bulk_update` and
`AsyncBaseRepository.bulk_update` validate their Core update values as well.
On updates, unloaded and unchanged attributes are skipped to avoid loading
deferred columns solely for validation. In-place mutations to a dict or list
are not written or validated unless the column uses SQLAlchemy mutable tracking
(for example, `MutableDict`) or the application assigns a new value.

## Detecting existing PostgreSQL JSON and JSON-over-TEXT values

For a `json` or `jsonb` column that may contain values written before this
validation was added, use a non-pattern search to obtain a cheap superset of
candidates:

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

For a JSON document stored through a `TypeDecorator` over `TEXT`, the `jsonb`
cast does not apply. Search the text column for the same escape sequence:

```sql
SELECT id, payload
FROM my_table
WHERE strpos(payload, chr(92) || 'u0000') > 0;
```

Then confirm each candidate by parsing it with `json.loads` and recursively
checking the parsed document for a real NUL byte. The text search is only a
superset here too: ordinary prose containing `\\u0000` is a false positive and
must not be treated as poisoned unless parsing reveals a real NUL byte.

## Performance

On this repository's benchmark, a 1,000-row insert with scalar string values
averaged 45.3018 ms. The same insert with a payload containing 100 nested JSON
items averaged 352.1811 ms, about 7.8 times as long and roughly 307 microseconds
of additional guard cost per row. Consumers storing large crawled JSON payloads
should account for this document-walk cost.
