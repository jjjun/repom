# Security Policy

This is the shared security review context for repom, including reviews by
Codex Security, Claude, and human maintainers. It describes intended boundaries
and properties to verify; it is not evidence that the implementation is secure
or that a scan has passed. It does not authorize execution, disclosure, or
changes. Development and review procedures belong in [AGENTS.md](AGENTS.md).

## System and Scope

repom is a Python library and collection of administrative CLI tools built on
SQLAlchemy and Alembic. It supplies model bases, synchronous and asynchronous
repositories, database/session management, migrations, diagnostics, and test
fixtures. Applications supply their own models, repositories, and API layer.
repom does not implement an HTTP service, user authentication, tenant identity,
or application authorization. Consumer applications may expose its operations
to untrusted users; lack of a server in this repository does not make those
library paths unreachable.

Repository-wide reviews include these surfaces and their supporting code:

| Surface | Source entry points | Assets and boundaries |
| --- | --- | --- |
| Models and queries | `repom/models/`, `repom/repositories/`, `repom/mixins/`, `repom/custom_types/`, `repom/nul_bytes.py`, `repom/exceptions.py`, `repom/__init__.py`, `repom/examples/` | Stored records, query scope, writable and serializable fields |
| Configuration and connections | `repom/config.py`, `repom/config_hook.py`, `repom/config_hooks/`, `repom/database.py`, `repom/exec_env.py`, `repom/postgres/config.py`, `repom/sqlite/`, `repom/redis/config.py` | Credentials, effective destination, TLS, session ownership |
| Discovery and migrations | `repom/utility.py`, `repom/scripts/db_sync_master.py`, `repom/scripts/debug_repository_queries.py`, `master_data_path` (default `data_master/`), `repom/examples/`, `alembic/`, `repom/alembic/`, `alembic.ini` | Python imports and file execution, schema/data integrity, migration namespaces and files |
| Administration and services | `repom/scripts/`, `repom/credentials.py`, `repom/postgres/`, `repom/postgres/docker-compose.template.yml`, `repom/redis/`, `repom/redis/docker-compose.template.yml`, `repom/docker_service.py`, `repom/docker_compose_safety.py` | Backup contents, subprocesses, secrets, containers, volumes, generated files |
| Logging, diagnostics, testing, and delivery | `repom/logging.py`, `repom/diagnostics/`, `repom/testing.py`, `tests/`, `.github/`, `.claude/hooks/session-start.sh`, `.claude/settings.json`, `.codex/config.toml`, `.mcp.json`, `.pre-commit-config.yaml`, `.vscode/tasks.json`, `scripts/`, `pyproject.toml`, `uv.lock` | Sensitive output, test isolation, dependency and build integrity |

SQLite and PostgreSQL, including the asynchronous drivers, are primary database
paths. Redis and pgAdmin management are also in scope. Examples, documentation,
and templates are relevant when they affect supported use or generated output.
Trace the active call path before treating a static template as a runtime default.

## Threat Model and Trust Boundaries

- Consumer request values, update dictionaries, search terms, pagination, and
  any exposed selector can be attacker-controlled. Stored values may originate
  from those inputs. Trace their route through the public API to the operation
  with security impact; state missing consumer context explicitly.
- Application code, model classes, SQLAlchemy expressions, custom repository
  overrides, and operator-selected configuration are trusted extension points.
  They run with the application's authority. A supported expression API is not
  a sandbox, but value-only APIs and explicit allowlists still need enforcement.
- `CONFIG_HOOK`, model locations, package prefixes, `alembic.ini`, migration
  scripts, engine factories, the master-data directory whose Python files
  `db_sync_master` executes, and module names passed to
  `debug_repository_queries` are operator/developer-controlled. `CONFIG_HOOK`
  may also be loaded from a `.env` file that `load_dotenv()` discovers. In
  particular, `alembic.ini` is trusted, code-equivalent configuration:
  `pre_migration_hook`, logging handler `class` and `args` used by `fileConfig`,
  `script_location` (which selects the migration `env.py`), `prepend_sys_path`,
  and `[post_write_hooks]` can load or execute code. Model discovery checks
  configured package names and `pre_migration_hook` checks its module component
  with raw string-prefix matching before importing; neither constrains which
  file supplies a module name, and the checks do not sandbox imported Python
  code. `CONFIG_HOOK` (including values loaded from `.env`), master-data files,
  and CLI-named debug modules are outside these checks.
  Receiving request data in one of these settings would cross a trust boundary
  and remains reportable.
- Consumers own authentication, record/tenant authorization, input schemas,
  field exposure, and limits at their application boundary. repom must preserve
  the predicates and restrictions passed to it. A dropped authorization filter
  can be a repom vulnerability even though repom does not create that filter.
- Database credentials, Docker access, backup directories, migration directories,
  and process environment are privileged operator resources. Do not assume an
  attacker can modify them without identifying that access and its prerequisites.
  Their trusted ownership does not excuse injection into generated formats,
  unintended file access, or disclosure to a less privileged observer.
- Restoring plain SQL runs the backup through `psql`. `psql` executes SQL with the
  restore role's database privileges and meta-commands with the OS privileges of
  the `psql` process (the host user or the container user). A SHA-256 sidecar
  detects a mismatch only when it is present. A missing sidecar logs a warning
  and the restore proceeds. It does not authenticate a backup when an attacker
  can replace or remove the sidecar.
- `basekit`, SQLAlchemy, Alembic, database drivers, database servers, and Docker
  are dependencies across this repository's boundary. Review repom's use of them
  and identify the owning dependency for upstream defects. No claim that their
  source was audited follows from a repom-only review.

## Security Invariants

The following are review requirements grounded in the current contracts. Each
requires source evidence and, where appropriate, focused validation on the
reviewed revision. A listed control or existing test is not proof of enforcement.

### Query scope and transactions

Unless a difference is stated below, these contracts apply to both
`BaseRepository` and `AsyncBaseRepository`.

- SQL values must not become syntax through interpolation. Dynamic identifiers
  and literals must be quoted for their actual, possibly nested SQL context,
  including a literal inside a dollar-quoted PostgreSQL `DO` body. Bound
  parameters do not protect identifiers. Review custom SQL compilation and CLI
  SQL generation (`repom/postgres/` and `repom/alembic/reset.py`) alongside
  repository queries.
- String `order_by` and `default_order_by` values use `column[:asc|desc]` and
  must pass the `allowed_order_columns` check (default: seven common names) and
  the model class-attribute lookup. String elements inside list/tuple ordering
  values are parsed and checked too. The lookup is not mapped-column
  resolution. SQLAlchemy expressions and non-string elements in sequences are
  trusted ordering inputs and bypass the string allowlist. Review
  `virtual_order_columns` and their caller handling as well.
- `get_by()`, `get_or_create()` lookups, and the `filter_by` arguments of
  `bulk_update()`, `bulk_delete()` and `bulk_permanent_delete()` resolve mapped
  columns and respect `allowed_filter_columns`; its default `None` permits every
  mapped column. These equality paths reject SQLAlchemy expressions as values.
  `filters` arguments are caller-supplied SQLAlchemy expressions and do not use
  this name-based resolver.
  `get_or_create()` also applies the default soft-delete filter, so a matching
  deleted row is treated as absent and a conflicting unique constraint can
  raise `IntegrityError`. `ManyToManyMixin` requires non-empty lookup fields and
  resolves lookup/link names to mapped columns, but it does not use
  `allowed_filter_columns` or check lookup values as plain values. The `id`
  values in `bulk_update()` rows bypass the equality resolver when `filter_by`
  is omitted. Its update keys have no allowlist and can update primary-key
  columns when `filter_by` or `filters` supplies the row selection.
- `get_by_id()` and the ID-based soft-delete methods validate IDs against
  SQLAlchemy expressions. `find_by_ids()`, `bulk_delete()` and
  `bulk_permanent_delete()` reject expression/ORM-attribute elements in their
  `ids` sequences. The default `_build_filters()` rejects `FilterParams` fields
  whose dumped value is non-`None` (including defaults) when no non-`None`
  mapping exists; overriding `_build_filters()` disables that check. Mapped
  non-string iterables become `IN` filters without a size cap. `MatchColumn`
  supports range comparisons and prefix/contains `LIKE`; the LIKE length limit
  defaults to 256 characters and can be configured per mapping.
- For soft-deletable models, `find()`, `find_one()`, `get_by()`, `get_by_id()`,
  `get_all()`, `find_by_ids()`, `count()`, `count_by_params()`, `bulk_update()`
  and soft `bulk_delete()` exclude deleted rows by default; `include_deleted`
  opts in where supported. `get_or_create()` also excludes deleted rows.
  `find_deleted()` and `find_deleted_before()` select deleted rows;
  `restore()` acts on deleted rows; `permanent_delete()`,
  `bulk_permanent_delete()` and `remove()` physically delete. Many-to-many target
  lookups and relationship/eager loads do not inherit repository soft-delete
  filtering. There is no repository-wide scoping hook: overriding `find()` does
  not constrain `get_by()`, `get_by_id()`, counts, bulk operations or
  `get_or_create()`. Consumers must not expose `include_deleted` without
  authorization.
- `limit` and `offset` receive type/range checks, and an explicit `limit` is
  checked against `max_limit` (default 1000, configurable to `None`). An omitted
  limit is not capped. Only `find()` warns when its limit is omitted;
  `get_all()`, `get_by(single=False)`, `find_by_ids()` and `find_deleted*()` do
  not warn and can return all matches. Offsets, `IN` list sizes, the number of
  per-row `bulk_update()` statements, and eager-loaded collection sizes from
  `options`/`default_options` are not otherwise bounded. `listjson_filter()`
  builds one correlated `EXISTS` per distinct requested value without a size cap.
- With an external session, sync and async repositories do not commit or roll
  back, but write paths flush. `remove()` may call `merge()`;
  `get_or_create()` opens a SAVEPOINT and issues raw `BEGIN` on SQLite; sync
  `bulk_update()` and `bulk_delete()` call `expire_all()` (the async methods do
  not). Since `bulk_update()` checks NUL bytes row by row, failure partway
  through can leave earlier statements in the caller's transaction. Async
  cancellation is shielded for internally owned session rollback and close in
  `DatabaseManager`; repository-level cancellation is not tested, and a cancel
  during commit leaves the outcome unknown.

### Model mutation and output

- `BaseModel.update_from_dict()` raises `ValueError` when both `allowed_fields`
  and the class's `updatable_fields` are `None`. An explicit `allowed_fields`
  replaces, rather than narrows, `updatable_fields`. It assigns only allowlisted
  ORM attribute keys from mapped `column_attrs`, including `column_property()`
  expressions, and always skips mapper-resolved primary-key attributes and the
  attribute keys `created_at`, `updated_at`, and a mapped `deleted_at`.
  `exclude_fields` can only narrow the allowlist. An empty set, or a string,
  can silently select no usable fields. Disallowed and unknown keys are ignored
  silently. The method does no type or NUL validation itself.
- These field-allowlist guarantees do not apply to model constructors, direct
  assignment, `dict_save()`, `dict_saves()`, `get_or_create()` lookup and
  defaults, `ManyToManyMixin.add_related_item()`, or `bulk_update()` in either
  repository implementation. `bulk_update()` can write any mapped column,
  including timestamps, `deleted_at`, and primary keys when `filter_by` or
  `filters` is used. Consumers must filter request data before these APIs. The
  inherited `BaseModel.__init__()` raises `TypeError` for `sensitive_fields`,
  `serializable_fields`, `updatable_fields`, and any keyword that is not a
  mapped attribute; it accepts every mapped attribute, so it is not a field
  allowlist. `to_dict()` and `update_from_dict()` read these controls from the
  class, so instance attributes cannot change them.
- `to_dict()` returns mapped column attributes, including deferred and
  `column_property()` values, excluding attribute keys in the class's
  `sensitive_fields`, even when they also appear in `serializable_fields`.
  `serializable_fields` can further limit returned columns. It does not serialize
  relationships or recurse. Logs, diagnostics, and consumer serializers are
  not filtered by `sensitive_fields`.
- NUL-byte validation runs from `BaseModel` mapper `before_insert` and
  `before_update` listeners during SQLAlchemy unit-of-work flushes, for sync and
  async sessions. Sync and async repository `bulk_update()` also validate plain
  values. Validation walks `str`, `dict`, `list`, and `tuple` values before
  binding. It does not cover `session.execute(insert(...)/update(...))`,
  including ORM bulk parameter lists, `bulk_insert_mappings()`,
  `bulk_save_objects()`, SQL-expression values in `bulk_update()`, or models
  based on plain `repom.database.Base`. Values written through other paths may
  contain NUL. A String-typed expression `column_property()` currently causes
  `_string_columns()` to raise `AttributeError` during each flush of that model;
  this fails closed.

### Connections and secret handling

- Each entry point's actual destination must match the resolved configuration,
  including `db_url`, `REPOM_DATABASE_URL` / `DATABASE_URL` overrides, and URL
  query or SQLAlchemy `connect_args` values for `host`, `hostaddr`, `service`,
  and `dsn`. `DatabaseManager`, `resolve_engine_settings()`, and synchronous
  diagnostics probes resolve these destination overrides; probes use the
  config object being checked. The shared `alembic/env.py` and `AlembicReset`
  build engines from `db_url` only. Synchronous test fixtures pass engine kwargs
  without the resolver, and consumer-built engines must opt into it. Review backup/restore
  host-tool and `docker exec` paths separately: URL-overridden client tools use
  the URL authority/path and reject query overrides for `host`, `hostaddr`,
  `service`, `dsn`, `port`, `dbname`, `database`, `user`, and `password`,
  regardless of the PostgreSQL URL driver name. Put those identity values in
  the URL authority/path where represented, or use an explicit client-tool
  configuration for other destination selectors;
  `sslmode` and `sslrootcert` remain supported query options. Rejection occurs
  before backup/restore Docker probes or client processes. The configured
  local-host path may target the managed container through `docker exec`;
  configured remote hosts use host client tools. Client-tool database names
  must not use libpq connection-string syntax. `database_info`
  reports configured `postgres_db` even when a URL override selects another
  database. In `prod`, destination resolution includes `PGHOST` and
  `PGHOSTADDR`, including `PGHOSTADDR` alongside an explicit URL host. A
  selected `PGSERVICE` or `service` setting is unresolved unless both `host`
  and `hostaddr` are explicit, so it requires strong TLS without parsing
  `pg_service.conf`. A host-less URL with no destination fallback remains
  local. Host client-tool subprocesses remove inherited `PGHOSTADDR` and
  `PGSERVICE` so those values cannot reroute their explicit `-h` target. `prod`
  and the normalized `production` alias receive equivalent guards. Unknown `EXEC_ENV`
  values warn once and use `dev` defaults for naming, TLS, and destructive
  command guards; `EXEC_ENV` is operator input, not proof of the real database's
  purpose.
- In `prod`, non-local PostgreSQL destinations require `sslmode` of at least
  `require`. `RepomConfig.db_url` and `postgres_tls_settings_for_url()` enforce
  URL TLS policy, while `postgres_tls_settings()` applies it to the configured
  host. `_resolve_postgres_engine_policy()` also checks `connect_args` and
  asyncpg's `ssl`; `DatabaseManager`, `resolve_engine_settings()`, and
  synchronous diagnostics probes use that resolver. The migration engine,
  `AlembicReset`, synchronous test fixtures, and consumer-built engines get
  only URL-level enforcement or none unless they call it. repom writes its
  resolved `sslmode` into generated and PostgreSQL override URLs, and into
  `PGSSLMODE` for host libpq client tools
  when a mode is resolved; `connect_args` TLS options override URL options. If
  URL and `connect_args` omit `sslmode`, `PGSSLMODE` is validated and propagated
  when no explicit `config.postgres.sslmode` is set. Loopback/socket and
  development defaults may permit plaintext.
- `require` alone is not a guarantee of certificate/hostname verification.
  Preserve explicitly selected `verify-ca`/`verify-full` semantics across driver
  adaptation. For libpq, absent `sslrootcert`, verification uses `PGSSLROOTCERT`
  or `~/.postgresql/root.crt`, not the system trust store. The asyncpg path
  passes a mode string through when no root certificate is configured; with an
  explicit root certificate, repom builds an `SSLContext` that does not load
  CRLs. Deployments needing authenticated remote peers must choose the
  corresponding verification settings and trust roots.
- Ordinary repr, logs, CLI status, diagnostics, and errors must not unexpectedly
  expose credentials. `safe_db_url()` masks userinfo passwords and a fixed set
  of query keys, including `dsn`; it is not a universal sanitizer. Alembic URL
  values are percent-escaped before ConfigParser handling. Still review
  malformed URLs: `RepomConfig.db_url` can fail in `make_url()` before
  `safe_db_url()` runs, and `repom_info.main` prints uncaught display errors;
  check parser exceptions for password fragments. An unencoded `@` can move a
  password fragment into the host, which appears in TLS errors and warnings.
  Restore `psql` stderr can contain SQL and backup data and is printed, logged,
  and included in `RestoreError`; only the exact configured password is
  masked. Include exception chains and failing child-process output in review.
- `engine_kwargs` defaults SQLAlchemy `hide_parameters` to `True`, but
  `SQLALCHEMY_HIDE_PARAMETERS` can disable it. The migration engine and
  `AlembicReset` do not set it. SQLAlchemy DEBUG echo can log result rows
  regardless of this option, and `debug_repository_queries` prints `to_dict()`
  values. `QueryAnalyzer` retains SQL and parameters, and SQL text can itself
  contain literals. No general redaction guarantee extends to every diagnostic
  artifact or application log.
- Redis helpers support plaintext `redis://` only, with no TLS option or
  production guard. Redis credentials travel in plaintext to the configured
  host, including the `repom_info` connectivity probe. pgAdmin's generated
  server entry uses `SSLMode: prefer`.

### Discovery and migrations

- Enforced import checks: model discovery validates each configured model
  package name before importing it, and `pre_migration_hook` validates its
  module component before loading the callable. Both use raw `startswith`
  matching. Prefixes should end in `.`, because a dotless prefix also admits
  sibling names. An empty prefix set disables the discovery check but rejects
  every hook. A string value for `allowed_package_prefixes` is iterated one
  character at a time. These checks validate names only; they do not select or
  constrain the file that supplies a name. `prepend_sys_path = .` in the default
  `alembic.ini` affects import resolution. `CONFIG_HOOK` (including values
  loaded from `.env`), master-data files executed by `db_sync_master`, and
  module names passed to `debug_repository_queries` are outside these checks.
- Hook behavior: the hook runs after logging `fileConfig` and model imports, but
  before Alembic connects, for both offline and online environment execution.
  It receives the live, process-wide `RepomConfig`; its return value is ignored
  and an exception aborts the command. The migration URL is set before the hook
  runs, so changing the config does not redirect that migration, though the
  mutation persists in the process. This non-redirection behavior is
  source-verified and has no focused test. `alembic_reset`, `db_create`,
  `db_delete`, and `db_sync_master` do not run the hook.
- Model imports and metadata: `env.py` and `db_create` reject model-module import
  failures. `configure_mappers` failures are logged but do not trigger strict
  import failure. The empty-metadata guard rejects zero discovered tables only
  when `model_locations` is non-empty. It does not detect unset locations,
  skipped modules, or omitted packages, any of which can lead autogenerate to
  propose `drop_table`. Discovery skips underscore-prefixed modules and
  excluded directories, and uses only the first path of a namespace package.
  Display-only discovery still imports model code and applies package checks.
  Review generated migrations.
- INI generation: path options reject newline, carriage return, NUL, and a
  leading `[`. `%` interpolation is intentionally allowed. Identifier options
  and each exclusion entry must match `[A-Za-z_][A-Za-z0-9_]*`. String-form
  `autogenerate_exclude_tables` values are split, trimmed, validated, and
  rejoined before they are written, so the emitted value has passed the same
  newline, carriage-return, NUL, and identifier checks. Template inputs must
  come from trusted configuration as specified in [AGENTS.md](AGENTS.md);
  validation does not make the generator an untrusted-configuration service.
- Runtime migration paths and namespace settings come from `alembic.ini`.
  `autogenerate_exclude_tables` accepts any table name; limiting it to sibling
  version tables is a review rule, not an enforced control. An exclusion matches
  a reflected table by unqualified name in any schema, suppressing that
  database-only table's removal drift from autogenerate and `alembic check`.
  Column drift is still compared. Do not list model tables. Review namespace
  version-table, schema, and version-file settings for each migration namespace.

### Administrative operations and files

- `db_delete`/`db_remove` and the `alembic_reset` CLI refuse `prod` and the
  normalized `production` alias. Outside production, they require a TTY `y`
  confirmation, or `--yes` when stdin is not a TTY; `--yes` does not skip a TTY
  prompt. These guards do not apply to other entry points:
  - `db_restore` has no environment refusal or `--yes` option. Its CLI confirms
    with `input()` and accepts piped stdin; a same-database restore asks for `y`,
    and a cross-database or unknown-source restore asks for the exact target
    name. The callable `restore_sqlite()`, `restore_postgresql()`,
    `restore_postgresql_via_host()`, and `restore_postgresql_via_docker()`
    helpers bypass those prompts and have no environment guard.
  - `db_sync_master` has no confirmation or environment guard. It executes the
    operator-controlled master-data Python files and upserts rows with
    `session.merge()`; it can run in production. Its callable
    `load_master_data_files()` executes those files and `sync_master_data()`
    upserts rows without a confirmation or environment guard as well.
  - `postgres_remove` and `redis_remove`, and their Python `remove()` helper
    paths, run Compose `down -v` without a confirmation prompt.
  - `postgres_rotate_credentials`, `redis_rotate_password`, and
    `pgadmin_rotate_password` default to a dry-run and require `--execute` to
    change credentials. The Python APIs
    `repom.postgres.credentials.rotate_postgres_credentials()`,
    `repom.redis.manage.rotate_password()`, and
    `repom.postgres.credentials.rotate_pgadmin_password()` also default to
    dry-run. pgAdmin volume recreation additionally requires both
    `--recreate-volume` and `--confirm-recreate-volume` with `--execute`; the
    `recreate_pgadmin_volume()` helper defaults to `confirm=False`.
  - `pg_restore_custom()` always invokes `pg_restore --clean --if-exists` and
    has no confirmation or environment guard.
  Review each entry point's target selection and confirmation contract.
- By default, `alembic_reset` drops the configured version table and then deletes
  top-level `*.py` files other than `__init__.py`, plus `__pycache__`, from every
  configured `version_locations` directory, including absolute paths. A failure
  partway through leaves a partial reset. The `AlembicSetup.reset_migrations`
  and `AlembicReset` Python APIs have no CLI confirmation guard.
- Test fixture factories accept normalized `EXEC_ENV=test`, an in-memory
  SQLite URL detected by the current `startswith("sqlite")` and
  `":memory:" in url` substring heuristic, or explicit
  `allow_destructive=True`, evaluated when the factory is called.
  `EXEC_ENV=test` permits any URL. These checks cannot prove a URL names
  disposable data; consumers must select a dedicated database.
- Backup, restore, retention, and migration-file cleanup must act on the intended
  target. Assess path construction, existing files, links, failure cleanup, and
  backup naming against a concrete attacker capability. `db_backup` and
  `pg_dump_custom()` create exclusive 0600 sibling partial files and publish the
  backup after success; both generate SHA-256 sidecars. PostgreSQL backup names
  are derived from the database name after rejecting path separators and `..`.
  The backup is published before its sidecar, so a missing sidecar warns and
  restore proceeds; a present but mismatched sidecar fails verification. The
  sidecar detects a mismatch only when present and does not authenticate a
  backup against replacement of both files.
- Backup files and generated secret files, including temporary and backup copies,
  contain sensitive data. Backup partial files and secret-file temporary siblings
  are created exclusively with POSIX mode 0600 before content is written, then
  atomically replaced into place. repom sets no Windows ACLs, and the compose
  directory itself is not restricted. Permission tests skip on Windows; POSIX
  mode bits alone are not evidence of equivalent Windows ACL isolation.
- Generated Compose/configuration/initialization content must not allow values
  to inject additional directives or SQL. Published service ports default to
  loopback; LAN exposure requires explicit configuration. Generation must retain
  the missing/placeholder-credential checks for enabled services.
- Generated Compose image references, container names, and named-volume names
  are validated before they reach the shared writer. Volume names must match
  Docker's named-volume syntax so they cannot become host bind mounts. Host-side
  bind-mount paths derived from configured data paths are not validated.
- Normal generation refuses missing or placeholder credentials for enabled
  services. Auto-start checks required `.env` keys and rejects a mismatch when
  the configured credential is non-empty and non-placeholder, but it does not
  independently reject empty or placeholder values stored in `.env`. Stop and
  remove rewrite generated files with credential validation disabled and do not
  validate the stored `.env` contents.
- Existing secret files must not be silently replaced with different credentials.
  Intentional regeneration and credential rotation must preserve their explicit
  execution/overwrite controls and consistent persistent configuration.
  PostgreSQL and Redis rotations validate generated configuration before changing
  the live credential, then persist `.env` after the live change. A persistence
  failure can leave the live and stored credentials inconsistent; these two
  commands print recovery steps. pgAdmin password rotation also changes the live
  password before regenerating files, and a persistence failure can leave them
  inconsistent.
- Subprocess argument, environment, stdin, and secret-file channels must preserve
  data boundaries and avoid unintended credential exposure. An argv list by
  itself does not establish safety against the invoked program's option parsing.
  Host PostgreSQL client tools receive the password through `PGPASSWORD`.
  PostgreSQL rotation sends SQL through stdin and supplies the current password
  through a mode-0600 env file passed with `docker exec --env-file`. The pgAdmin
  update command carries its password in argv; Redis rotation's explicit
  `--new-password` and `--old-password` options also expose values in argv.
  The Redis health check uses `redis-cli ping` with `REDISCLI_AUTH` from the
  Compose service environment, not a password CLI flag. Docker exposes service
  environment values through `docker inspect`. Some `docker exec` paths pass a
  configured container name without rejecting a leading `-`. Client-tool
  database arguments reject libpq connection-string and URI forms, but argv
  lists alone do not prevent option parsing by the invoked program.
- The packaged `repom/postgres/docker-compose.template.yml` and
  `repom/redis/docker-compose.template.yml` files are not read by the runtime
  Compose generators. Review their contents separately if a consumer uses them
  directly.

## Reportable Findings and Severity Context

A finding needs a concrete broken property and a plausible path from an actor
with the stated capabilities to confidentiality, integrity, or availability
impact. Record the affected revision, source locations, input/control path,
required configuration and privileges, affected backend/driver, validation
performed, remaining uncertainty, and a bounded remediation.

Prioritize unauthorized data access or mutation, SQL/configuration/command
injection, secret disclosure, destructive target confusion, and bypasses of
applicable transport or import controls. Explain severity using actual exposure,
required access, affected data, and blast radius. An unauthenticated consumer
path and an operator-only local command should not automatically receive the
same severity. Classify a crash or performance issue as a security finding only
with an explained availability impact and plausible attacker influence.

Evidence may be static, dynamic, or both. Distinguish a demonstrated issue from
an unresolved candidate; tests that merely mention a control do not validate it.
Use sanitized reproductions and record review coverage and deferred paths.
An empty findings list is not a security certification.

## Scope Limits and Risk Decisions

- Application-specific authentication and tenant policy are consumer-owned.
  Their absence in this foundation alone is not a repom defect. Failures to
  preserve supplied controls, and unsafe documented integration behavior, remain
  reviewable here.
- Execution of intentionally supplied Python hooks, migrations, or trusted SQL
  expressions is expected capability. A lower-trust route into those execution
  paths, or a bypass of an explicit restriction, is a separate finding.
- The trusted-expression exclusion applies only to `ClauseElement` or
  ORM-attribute objects supplied by application code. It does not cover plain
  strings, including strings inside sequences, dicts, or other containers, that
  reach a parser or SQLAlchemy label/attribute resolution. Reviews must identify
  each expression-accepting parameter (for example, `order_by` sequences,
  `filters`, `options`, `filter_by`/`get_by` values, and `ids`).
- Deliberately selected administrative operations and documented overrides need
  their preconditions checked. The mere existence of a destructive API is not
  evidence of unauthorized access; unintended targets or bypassed safeguards are.

These limits describe existing ownership and API contracts. This policy does
not accept any specific vulnerability, waive review of a directory, or suppress
a finding because a control is documented. New exclusions, severity caps, and
risk acceptance require an explicit maintainer decision with rationale and
revisit conditions. Unconfirmed assumptions must remain visible as uncertainty.

## Known Limitations and Evidence Maintenance

Actual consumer exposure, attacker access to local directories, database roles,
and required TLS identity guarantees are deployment-specific and not established
by this repository. Record them for the particular review instead of assuming
all callers or files are trusted. A release support/backport policy and a private
vulnerability reporting channel also require maintainer confirmation; this file
does not invent either.

Existing tests provide useful evidence entry points: `test_update_from_dict.py`,
`test_sensitive_fields.py`, `test_repository_pagination_limits.py`,
`test_repository_session_isolation.py`, `test_database_engine_settings.py`,
`test_async_database.py`, `test_database_url_masking.py`,
`test_alembic_templates.py`, `test_docker_compose_safety.py`,
`test_create_test_fixtures_safety.py`, and the administrative-command tests under
`tests/unit_tests/`, plus migration behavior tests under `tests/behavior_tests/`.
They do not replace source review or prove every platform/driver path is covered.
CI runs on Ubuntu only. File-permission tests skip on Windows, and repom sets no
Windows ACLs. The PostgreSQL integration job exercises only the synchronous
psycopg path. asyncpg TLS adaptation, client-tool TLS, and Docker paths are
covered by unit tests with fakes.

The dependency audit workflow checks known advisories on dependency changes and
weekly. This does not establish that a dependency is safe or audit private/git
dependency source. For `basekit`, the resolved commit in `uv.lock` is the effective
pin while `pyproject.toml` selects a Git branch. Update this policy when public
contracts, dependencies, defaults, or deployment assumptions change. Keep policy
drift and hardening proposals distinct from validated code vulnerabilities.
