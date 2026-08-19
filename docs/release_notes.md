# Release notes

## Unreleased

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
