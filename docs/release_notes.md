# Release notes

## Unreleased

- Fixed `get_async_db_session()` and `get_async_db_transaction()` losing the
  caller's exception during cleanup. Both `Depends` dependencies drove their
  underlying async context manager through a private adapter class with
  `async for`; when the consumer raised inside the dependency's scope (as
  FastAPI does at the `yield` when an endpoint raises), the exception was
  never forwarded into the adapter's inner async generator. The adapter's
  `async with` block then only exited later, when the event loop's
  async-generator finalizer ran `aclose()` in a background task, so the
  session was rolled back with `GeneratorExit` instead of the endpoint's
  exception, after the response had already been sent. Both dependencies are
  now plain async generators that wrap the context manager directly
  (`async with ...: yield ...`), so a thrown exception enters the
  `async with` block immediately and rollback runs, with the original
  exception, before it reaches the caller. `get_db_session()` and
  `get_db_transaction()` did not have this bug - they used `yield from` over
  the adapter, which already forwarded thrown exceptions into the delegated
  generator - but are simplified to the same `with ...: yield ...` shape with
  no behavior change. The now-unused private adapter classes
  `_ContextManagerIterable` and `_AsyncContextManagerIterable` are removed.
  Commit-on-success and rollback-on-error semantics are unchanged.
- Added `get_reusable_async_transaction()`, the async counterpart of
  `get_reusable_sync_transaction()`. It returns
  `DatabaseManager.get_async_transaction()` directly (an async context
  manager that commits on success and rolls back on error) without disposing
  the engine on exit, for worker/task code that runs multiple transactions
  in the same process. The async repository guide now recommends
  `async with get_reusable_async_transaction() as session:` for that case
  instead of iterating `get_async_db_transaction()` with `async for`, which
  had the same delayed-cleanup problem as the dependency bug above whenever
  the loop body raised.
- Fixed `AutoDateTime` silently shifting timezone-aware values with a non-UTC
  offset. `process_bind_param` only attached `timezone.utc` to naive values
  and passed aware values through unchanged; on a backend that cannot retain
  an offset (SQLite stores only the wall-clock component of `DateTime`), an
  input such as `2026-01-01T12:00:00+09:00` came back as
  `2026-01-01T12:00:00+00:00` — the same wall time relabelled as UTC, nine
  hours off the original instant. This also affected comparison filters (for
  example `Model.created_at >= <aware value>`) on SQLite, since the bound
  value went through the same unconverted path as stored values. Aware values
  are now normalized with `value.astimezone(timezone.utc)` before binding, so
  the instant is preserved regardless of the input offset. Naive and `None`
  inputs, and all `process_result_value` behavior, are unchanged. Rows written
  before this fix keep their already-shifted wall time; there is no data
  migration for existing rows.
- `PostgresConfig.host` and `RedisConfig.host` now default to `127.0.0.1`
  instead of `localhost`. `postgres_generate` / `redis_generate` already
  publish container ports on `127.0.0.1` only, but a client default of
  `localhost` still resolves through the OS, and on hosts where `localhost`
  resolves to `::1` before `127.0.0.1` (Windows, and many Linux setups with
  `::1` in `/etc/hosts`) every connection first tries `::1`, is refused, and
  only then falls back to `127.0.0.1`. That round trip alone can exceed a
  short client-side connect timeout (arq's `RedisSettings.conn_timeout`
  defaults to 1s) and made a freshly generated container look unreachable.
  `POSTGRES_HOST` / `REDIS_HOST` environment overrides and config hooks keep
  working unchanged; a project that pins `config.postgres.host` or
  `config.redis.host` back to `localhost` explicitly should set it to
  `127.0.0.1` instead (or otherwise account for the IPv6-first delay).
  `_POSTGRES_LOCAL_HOSTS` still treats `localhost`, `127.0.0.1`, and `::1` as
  equivalent for the prod `sslmode` exemption.
- Fixed `listjson_filter()` on PostgreSQL. It built its per-value filter with
  `func.json_each(model_column).table_valued(...)`, but PostgreSQL's
  `json_each()`/`json_each_text()` only accept JSON objects and raise
  `cannot deconstruct an array as an object` against a `ListJSON` column's
  JSON array, and `json_each()`'s `value` column is typed `json`, which has
  no equality operator against a bound string
  (`operator does not exist: json = character varying`). The empty-list
  branch (`model_column == []`) hit the same missing `json` equality
  operator. `listjson_filter()` now compiles to `json_array_elements_text()`
  for the element match and `json_array_length(...) == 0` for the empty-list
  match on PostgreSQL, resolved at SQL-compile time so callers do not need to
  branch on dialect; SQLite is unaffected and keeps using `json_each()`.
- Fixed `listjson_filter()` duplicating model rows. It added one table-valued
  `json_each`/`json_array_elements_text()` expansion per requested value
  directly to the outer query, so a repeated array element or several
  requested values multiplied the outer row for each match instead of
  filtering it. This inflated `count()` and could push a matching row past a
  `limit`/`offset` page. Each distinct requested value now compiles to a
  correlated `EXISTS` against the expansion instead, so the outer query's
  `FROM` still lists only the model table and matches are never duplicated.
- `postgres_sslmode` now picks its prod default per host. When `postgres.host`
  is `localhost`, `127.0.0.1` or `::1` the default is `prefer` even in prod;
  any other host still defaults to `require`. The PostgreSQL container that
  `postgres_generate` produces (`postgres:16-alpine`) does not enable SSL, so a
  host-independent `require` default made a prod deployment that talks to that
  container fail on its next restart with `server does not support SSL, but
  SSL was required`. An explicit `config.postgres.sslmode` is unaffected. Engine
  creation logs a warning when a prod connection resolves to a non-require
  sslmode.
- BREAKING: `config.model_import_strict` now defaults to `True` instead of
  `False`. `load_models()` discarded the failure list `import_from_packages()`
  returned, so a model module that failed to import was silently absent from
  `Base.metadata` — `alembic revision --autogenerate` would then propose
  `op.drop_table` for that model's table, and `db_create` would skip creating
  it, with no error either way. `load_models()` now returns the
  `DiscoveryFailure` list and logs every failure at ERROR with the module
  name and exception. `alembic/env.py` and `db_create` now call
  `load_models(strict=True)`, so they raise on any import failure regardless
  of `config.model_import_strict`; `alembic/env.py` also refuses to run when
  `model_locations` is configured but discovery finds zero models. Projects
  that rely on best-effort model loading in other entry points can still set
  `config.model_import_strict = False` explicitly. `repom_info` now lists any
  import failures under a new "Model Import Failures" section instead of
  swallowing them.
- BREAKING: `create_test_fixtures()` / `create_async_test_fixtures()` now
  default `db_url` to in-memory SQLite (`sqlite:///:memory:`) instead of
  `config.db_url`, and raise `RuntimeError` when the resolved database is
  neither in-memory SQLite nor `EXEC_ENV=test`. A consuming project's test
  suite running with `EXEC_ENV` unset or left at its `dev` default previously
  created tables in - and then dropped - its real dev/prod database at
  session teardown. Pass `allow_destructive=True` to explicitly opt into
  targeting a real database. `db_delete` and `alembic_reset` now also refuse
  to run when `EXEC_ENV=prod`, and require an interactive `y` confirmation
  (or `--yes` when stdin is not a TTY) before dropping tables or resetting
  migrations; both print the masked target database URL first.
- BREAKING: `alembic/env.py` now validates the `pre_migration_hook` module
  against `allowed_package_prefixes` before importing it; a hook that lives
  outside those prefixes raises `ValueError` at migration time. Add the
  hook's package prefix to `config.allowed_package_prefixes` in your config
  hook. `AlembicTemplates.generate_alembic_ini` also rejects control
  characters and non-identifier values in the options it writes.
- BREAKING: `BaseModel.update_from_dict()` now requires an explicit
  allowlist. Pass `allowed_fields`, or set the class attribute
  `updatable_fields`, or the call raises `ValueError`. Previously every
  mapped column except `id`, `created_at`, and `updated_at` was writable,
  which made the method a mass-assignment sink for any column a consuming
  project added (`is_admin`, `tenant_id`, `deleted_at`, and so on).
  Primary-key columns are now resolved from the mapper instead of the
  literal name `id`, so a primary key declared under any other name is also
  excluded unconditionally, along with `created_at`, `updated_at`, and
  `deleted_at` (when the model has it) — even if listed in
  `updatable_fields` or `allowed_fields`. `BaseModel.to_dict()` still
  returns every column by default; set the new `sensitive_fields` class
  attribute to exclude specific columns (such as password hashes) from the
  output, and optionally `serializable_fields` to return only an explicit
  subset.
- BREAKING: `get_all()` now excludes soft-deleted rows by default, matching
  every other read method on the repository, and accepts
  `include_deleted: bool = False` to opt back into the previous behaviour.
  `get_all()` also now applies the repository's default ordering
  (`default_order_by` when set, otherwise `id` asc for models that have an
  `id` column; models declared with `use_id=False` and no `default_order_by`
  keep returning rows in unspecified order) instead of always returning rows
  in unspecified order. Consuming projects that relied on `get_all()`
  returning soft-deleted rows must pass `include_deleted=True` explicitly.
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
- BREAKING: `postgres_generate` and `redis_generate` now publish container
  ports on `127.0.0.1` by default instead of `0.0.0.0`; set
  `POSTGRES_EXPOSE_TO_LAN` / `PGADMIN_EXPOSE_TO_LAN` / `REDIS_EXPOSE_TO_LAN`
  to restore LAN-wide access for projects that need it. `POSTGRES_PASSWORD`,
  `PGADMIN_DEFAULT_PASSWORD`, and `REDIS_PASSWORD` are no longer written into
  the generated `docker-compose.generated.yml`; they are written to a
  generated `.env` file (mode 0600) that Compose loads from the same
  directory. The generated `redis.conf` no longer contains `requirepass`;
  when a Redis password is configured, the container's `command` reads it
  from the service environment (`--requirepass "$$REDIS_PASSWORD"`) instead.
- BREAKING: `postgres_generate` and `redis_generate` refuse to run when the
  configured password is unset or still the literal `CHANGE_ME` placeholder,
  raising a `ValueError` that names the environment variable to set.
  `PostgresConfig.password` and `PgAdminConfig.password` now default to
  `CHANGE_ME`, a non-functional placeholder, instead of the working literals
  `repom_dev` and `admin`. Generated Redis services now always require a
  password.
