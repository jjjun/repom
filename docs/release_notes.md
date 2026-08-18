# Release notes

## Unreleased

- NUL bytes in `String` and `Text` columns now raise `NulByteError` on every
  supported dialect, including SQLite. SQLite-backed consumers that previously
  stored NUL bytes must reject or sanitize those values before persistence.
