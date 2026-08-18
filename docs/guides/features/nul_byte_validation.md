# NUL byte validation

repom rejects values containing a NUL byte (`0x00`) in `String` and `Text`
columns before they reach the database. It raises `NulByteError`, which names
the column and byte offset so applications can map the error to a 4xx response.

The guard runs for inserts and updates of `BaseModel` subclasses in every
SQLAlchemy session. `BaseRepository.bulk_update` and
`AsyncBaseRepository.bulk_update` validate their Core update values as well.
On updates, unloaded and unchanged string attributes are skipped to avoid
loading deferred columns solely for validation.

`CustomJSON` and `ListJSON` payloads are intentionally excluded. Their JSON
encoding represents a NUL as an escape sequence and does not send a real NUL
byte to PostgreSQL `json` columns. repom does not provide a JSONB type.

`StrEncodedArray` validates its encoded text value separately. Because its
bind processor has no mapped-column context, `NulByteError.column_name` is
`StrEncodedArray`. Its offset is into the comma-joined encoded string, not an
individual list element.
