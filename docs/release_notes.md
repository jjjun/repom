# Release notes

## Unreleased

### Breaking

- BREAKING: `AutoDateTime` subclasses `UTCDateTime` and normalizes datetime values to
  UTC on bind and result. Timezone-aware values are converted to UTC before storage,
  preserving the represented instant on SQLite and in comparison filters, and read back
  as timezone-aware UTC values; naive values are labeled UTC.
  `SoftDeletableMixin.deleted_at` therefore reads as a timezone-aware UTC datetime on
  SQLite, so consumers comparing it should use timezone-aware UTC values.
- BREAKING: `create_test_fixtures()` and `create_async_test_fixtures()` default to
  in-memory SQLite instead of `config.db_url`, and reject a non-memory database unless
  normalized `EXEC_ENV` is `test`. Pass `allow_destructive=True` to target another
  database intentionally. `db_delete` and `alembic_reset` also reject production
  environments and require confirmation before destructive work.
- BREAKING: `repom.scripts.db_backup.main()` and `repom.scripts.db_restore.main()` now
  raise on failure instead of printing an error and returning normally. Backup and
  restore path failures raise `BackupError` or `RestoreError` after removing any partial
  output; user cancellation in `db_restore` still returns normally.
- BREAKING: NUL bytes in `String`, `Text`, `JSON`, `CustomJSON`, `ListJSON`,
  `ARRAY(String)`, and `TypeDecorator` columns backed by a String type raise
  `NulByteError`, including nested JSON keys and values. Consumers with existing SQLite
  string data must reject or sanitize NUL bytes before persistence. To find existing
  PostgreSQL `json` values, use `strpos(payload::text, chr(92) || 'u0000') > 0` as a
  candidate filter and confirm by casting to `jsonb`; for JSON stored in TEXT, parse
  candidate rows with `json.loads` and recursively check for an actual NUL byte. Both
  filters can match ordinary prose containing the escape sequence. The consumer must
  inspect, repair, or remove existing affected rows before upgrading.
- BREAKING: `PostgresConfig.host` and `RedisConfig.host` default to `127.0.0.1` instead
  of `localhost`. Explicit `POSTGRES_HOST` / `REDIS_HOST` overrides remain available.
- BREAKING: Repositories without eager-loading defaults expose `default_options == ()`
  instead of `[]`; tuple load options are accepted alongside lists.
- BREAKING: `config.model_import_strict` defaults to `True`. `load_models()` returns
  discovery failures and logs each one; Alembic and `db_create` load strictly, and
  Alembic refuses an empty discovery result when `model_locations` is configured.
  `repom_info` lists import failures. Set `config.model_import_strict = False` only for
  entry points that intentionally allow best-effort loading.
- BREAKING: Alembic validates a configured `pre_migration_hook` module against
  `allowed_package_prefixes` before importing it. Add the consumer hook's package prefix
  to that setting. `AlembicTemplates.generate_alembic_ini` rejects control characters
  and invalid identifiers in values written to the ini.
- BREAKING: `BaseModel.update_from_dict()` requires an explicit field allowlist through
  `allowed_fields` or `updatable_fields`. Primary keys, `created_at`, `updated_at`, and
  `deleted_at` remain excluded. `BaseModel.to_dict()` still returns all columns by
  default and supports `sensitive_fields` and `serializable_fields` to limit serialized
  values.
- BREAKING: `get_all()` excludes soft-deleted rows by default and applies repository
  default ordering; pass `include_deleted=True` to include deleted rows. `bulk_update()`
  also excludes soft-deleted rows by default. `bulk_update()` and `bulk_delete()` reject
  an empty resolved filter unless `allow_unfiltered=True`; filter keys and IDs are
  resolved through the model mapper.
- BREAKING: `find()` combines `params` and `filters` with AND. The default
  `_build_filters()` raises `ValueError` when a non-None `FilterParams` field has no
  non-None `field_to_column` mapping.
- BREAKING: Removed `JSONEncoded` and `StrEncodedArray`. Use `CustomJSON` for
  object-like JSON and `ListJSON` for list values. Historical migrations that used
  either type only for a TEXT column can use `sa.TEXT()` instead.
- BREAKING: `field_to_column` string fields now use exact `==` matching instead of
  unescaped substring matching. Use `contains_column()` or `prefix_column()` for
  substring or prefix search; both escape `%` and `_` and enforce `max_length` (default
  256).
- BREAKING: `ListJSON` stores JSON arrays instead of double-encoded JSON strings. Reads
  remain compatible with both formats, but `listjson_filter()` and `column == []` only
  match the new format. Rewrite existing rows before relying on those filters: SQLite
  can use `UPDATE t SET col = json(json_extract(col, '$')) WHERE json_type(col) =
  'text'`; PostgreSQL `json` can use `UPDATE t SET col = (col #>> '{}')::json WHERE
  json_typeof(col) = 'string'`.
- BREAKING: `postgres_generate` and `redis_generate` bind published ports to `127.0.0.1`
  by default. Set `POSTGRES_EXPOSE_TO_LAN`, `PGADMIN_EXPOSE_TO_LAN`, or
  `REDIS_EXPOSE_TO_LAN` to enable LAN access. Generated compose files no longer contain
  `POSTGRES_PASSWORD`, `PGADMIN_DEFAULT_PASSWORD`, or `REDIS_PASSWORD`; these secrets
  are written to a mode `0600` `.env` file. Redis `requirepass` is supplied through the
  service environment, not `redis.conf`.
- BREAKING: `postgres_generate` and `redis_generate` reject unset or literal `CHANGE_ME`
  passwords. `PostgresConfig.password` and `PgAdminConfig.password` default to that
  non-functional placeholder, and generated Redis services always require a real
  password.
- BREAKING: `repom.logging.get_logger(name)` no longer adds another `repom.` prefix when
  `name` is `repom` or already starts with `repom.`. Internal logger names now match
  their module paths.

### Fixed

- Async session cleanup now retrieves completed shielded tasks, so commit failures
  propagate and pending writes roll back when an eager task factory is active.
- Database engines and session factories are disposed when a lifespan body exits
  with an exception or cancellation.
- Production PostgreSQL TLS validation now follows effective `host` / `hostaddr`
  destinations from URL query parameters and engine `connect_args`, including
  comma-separated host lists. Remote destinations require `require` or stronger;
  asyncpg rejects unsupported `hostaddr` overrides and production DSN overrides
  are rejected when their destination cannot be validated safely.
- Async PostgreSQL engine settings now translate supported libpq-style options from
  URL query parameters and `connect_args`, with `connect_args` taking precedence over
  URL values. They preserve native asyncpg options, merge `server_settings`, pass
  certificate options through the asyncpg DSN, and retain SQLAlchemy dialect options
  such as `prepared_statement_cache_size`. Unsupported or conflicting options raise
  a clear error during engine configuration.
- Autogenerated Alembic revisions now import repom custom-type modules so revisions
  using types such as `UTCDateTime` and `ListJSON` run without manual import edits.
- Database URLs shown in logs and diagnostics mask PostgreSQL `sslpassword`, OAuth client
  secrets, SCRAM keys, and the existing password query parameters, including repeated,
  case-variant, and percent-encoded parameter names.

### Added

- The basekit source follows branch `main`; `uv.lock` is the effective dependency pin.
- `RepomConfig` can configure Alembic `script_location`, `version_locations`,
  `version_table`, and `version_table_schema` when `alembic_init` creates an ini file.
- Alembic reset and credential rotation entry points accept explicit arguments for task
  runners. `main_postgres(argv=None)`, `main_pgadmin(argv=None)`, and
  `main_rotate_password(argv=None)` accept argv lists;
  `rotate_postgres_credentials_cli`, `rotate_pgadmin_credentials_cli`, and
  `rotate_redis_password_cli` expose keyword-callable functions.
  `reset_alembic_migrations`, `describe_alembic_reset`, and
  `debug_repository_queries_cli` are also available as reusable functions.
- Test fixture factories can bind and restore the global database manager with
  `DatabaseManager.bind_engine_for_tests()` through `bind_global_manager=True`. This
  behavior is separate from the factory's transaction rollback fixtures.
- Shared environment override helpers include `apply_repom_env_overrides()` and the
  public parsers in `repom.config_hooks.parsing` (also available through the `_parsing`
  alias). `RedisConfig` provides `connection_kwargs()`, `url()`, and `safe_url()` for
  client settings and credential-safe logging.
- Repositories add arbitrary SQLAlchemy filters to bulk update and delete methods,
  `bulk_permanent_delete()` for physical deletion of matching rows, `FilterParams`
  support in `count()` and `find_deleted()`, range operators for `field_to_column`, and
  SAVEPOINT-backed `get_or_create()` in sync and async variants.
- `get_reusable_sync_session()` and `get_reusable_async_session()` support
  caller-managed session lifetimes. They never commit; closing the session discards an
  open transaction without expiring loaded objects, so loaded attributes remain readable
  after exit while lazy loads still require an active session. Closing the session does
  not dispose the reusable engine. The async session helper does not change the
  commit-on-success behavior of the FastAPI dependency `get_async_db_session()`.
- Repository defaults follow normal Python attribute lookup, so instance values for
  `default_options`, `default_order_by`, `max_limit`, and `field_to_column` override
  class values.
- CI runs `test.yml` on pushes and pull requests, with a dedicated
  `postgres-integration` job. GitHub Actions are pinned to commit SHAs, with Dependabot
  configured to update them.

### Changed

- Logging defaults now use basekit 0.7.0's normalized `EXEC_ENV`; the minimum basekit
  version is 0.7.0. `test` (including surrounding whitespace and mixed case) selects
  the test configuration and fixture guard; `production` is an alias for `prod` for
  PostgreSQL database names, TLS defaults and enforcement, and destructive-operation
  guards.
  Unknown values warn and use the dev database name/file for PostgreSQL and SQLite.
- A non-empty `REPOM_DATABASE_URL` takes precedence over `DATABASE_URL`; an empty value
  falls through to `DATABASE_URL`. A URL override determines `db_type`, sets
  `config.db_url_overridden`, and selects the target for `db_backup`, `db_restore`,
  `db_create`, `db_delete`, and `db_sync_master`. A mismatching `DB_TYPE` produces one
  warning and the URL backend wins. File-based SQLite overrides use the URL path, and
  in-memory SQLite backup/restore is rejected. PostgreSQL TLS defaults are `require` for
  remote production hosts and `prefer` otherwise, including hostless URLs; `sslrootcert`
  is added when configured, the URL omits `sslmode`, and the URL lacks `sslrootcert`.
  Weak modes (`disable`, `allow`, `prefer`) raise for remote production hosts. Engine
  creation warns when the effective URL in production does not enforce TLS. PostgreSQL
  backup and restore details are in the backup guide; `db_sync_master` skips managed
  containers as documented in the master data sync guide.
- PostgreSQL and Redis credential rotation apply changes to existing services and
  persist successful new secrets into the compose directory `.env`. PostgreSQL grants
  are applied before changing the current role password; replacement-user rotation
  updates both configured username and password. pgAdmin rotation can recreate its own
  volume without removing PostgreSQL data. Docker service auto-start reuses existing
  compose files and `.env` when available. Explicit generation/start commands refuse to
  replace a differing `.env` unless `--force-regenerate` is supplied; changed content
  keeps the old file as `.env.bak` with mode `0600`.
- PostgreSQL backup and restore share host and Docker command construction and stream
  data between files and database tools instead of buffering full archives in memory.
  Backups stream `pg_dump` output through gzip to a mode `0600` partial file; restores
  stream decompressed input to `psql`, fully validate plain SQL archives before starting
  `psql`, and no longer depend on external `gunzip`. Stderr draining avoids a `pg_dump`
  pipe deadlock. PostgreSQL plain-SQL restores disable user `psqlrc` settings, stop at
  the first SQL error, and run in one transaction; custom-format restores also use one
  transaction. The backup guide documents the plain-dump large-object transaction
  limitation. PostgreSQL backups use `<database>_<YYYYmmdd_HHMMSS>.sql.gz` names (the
  connected database, which is the URL database when the URL is overridden);
  SQLite and PostgreSQL rotation and incomplete-file cleanup match the exact database
  name and timestamp. `db_restore` lists the target database's backups first, reports
  source and target, and requires typing the target name to confirm a backup with an
  unknown or different source; legacy `db_*.sql.gz` files remain listed but are not
  automatically rotated or deleted. Backup and restore use effective URL credentials and
  TLS settings and avoid probing the managed container when host tools apply. The file
  formats are unchanged.
- Repository queries order by all primary-key attributes by default. String `order_by`
  values use remaining primary-key attributes as same-direction tie-breakers; explicit
  SQLAlchemy expressions define the complete ordering. `get_by(..., single=True)`
  returns the matching row with the lowest primary key, independent of
  `default_order_by`.
- Alembic reset reads `version_table`, `version_table_schema`, `version_locations`, and
  `script_location` from the selected ini through `AlembicSetup.from_ini`. Its
  confirmation shows the resolved table and version directories. `alembic_init` uses an
  existing ini when creating version directories; the minimum Alembic version is now
  `1.16.0`.
- The shared Alembic environment preserves existing application and Repom loggers when
  configuring Alembic logging in-process. SQLAlchemy echo setters immediately
  reconfigure the `sqlalchemy.engine.Engine` logger and return it to `WARNING` when echo
  is disabled; `_setup_sqlalchemy_logging` is no longer public.
- Running `sync_master_data` twice with identical data, assigning a column its current
  value, or changing only a relationship no longer bumps `updated_at`. Explicitly
  assigned `updated_at` values are preserved.
- The default test-environment hook selects SQLite only when normalized `EXEC_ENV` is
  `test`; other environments use PostgreSQL. Tests normalize `EXEC_ENV` consistently
  before deciding whether in-memory SQLite and the destructive fixture guard apply.

### Fixed

- Fixed FastAPI lifespan integration: `get_lifespan_manager()` returns a callable
  lifespan handler, so `FastAPI(lifespan=get_lifespan_manager())` works; the manager's
  `app` argument remains optional for direct context use.
- Fixed sync and async database dependencies so exceptions from a yielded endpoint reach
  the context manager immediately and trigger rollback before the exception returns to
  the caller. Added `get_reusable_async_transaction()` for worker code that needs
  commit-on-success and rollback-on-error transactions without disposing the engine.
- Fixed `listjson_filter()` on PostgreSQL to use `json_array_elements_text()` for
  element matching and `json_array_length()` for empty arrays. Matching now uses
  correlated `EXISTS` expressions, so repeated values do not duplicate model rows or
  inflate counts and pages.
