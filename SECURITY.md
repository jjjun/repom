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
| Models and queries | `repom/models/`, `repom/repositories/`, `repom/mixins/`, `repom/custom_types/`, `repom/nul_bytes.py` | Stored records, query scope, writable and serializable fields |
| Configuration and connections | `repom/config.py`, `repom/config_hook.py`, `repom/config_hooks/`, `repom/database.py`, `repom/exec_env.py`, backend config modules | Credentials, effective destination, TLS, session ownership |
| Discovery and migrations | `repom/utility.py`, `alembic/`, `repom/alembic/`, `alembic.ini` | Python imports, schema/data integrity, migration namespaces and files |
| Administration and services | `repom/scripts/`, `repom/credentials.py`, `repom/postgres/`, `repom/redis/`, `repom/docker_service.py`, `repom/docker_compose_safety.py` | Backup contents, subprocesses, secrets, containers, volumes, generated files |
| Logging, diagnostics, testing, and delivery | `repom/logging.py`, `repom/diagnostics/`, `repom/testing.py`, `tests/`, `.github/`, `scripts/`, `pyproject.toml`, `uv.lock` | Sensitive output, test isolation, dependency and build integrity |

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
  scripts, and engine factories are operator/developer-controlled. In particular,
  `alembic.ini` is trusted code-equivalent configuration. Receiving request data
  in one of these settings would cross a trust boundary and remains reportable.
  A package-prefix check does not sandbox imported Python code.
- Consumers own authentication, record/tenant authorization, input schemas,
  field exposure, and limits at their application boundary. repom must preserve
  the predicates and restrictions passed to it. A dropped authorization filter
  can be a repom vulnerability even though repom does not create that filter.
- Database credentials, Docker access, backup directories, migration directories,
  and process environment are privileged operator resources. Do not assume an
  attacker can modify them without identifying that access and its prerequisites.
  Their trusted ownership does not excuse injection into generated formats,
  unintended file access, or disclosure to a less privileged observer.
- Restoring SQL executes the selected backup's contents with database privileges.
  Operators must establish backup provenance. A SHA-256 sidecar detects a mismatch;
  it does not authenticate a backup when an attacker can replace both files.
- `basekit`, SQLAlchemy, Alembic, database drivers, database servers, and Docker
  are dependencies across this repository's boundary. Review repom's use of them
  and identify the owning dependency for upstream defects. No claim that their
  source was audited follows from a repom-only review.

## Security Invariants

The following are review requirements grounded in the current contracts. Each
requires source evidence and, where appropriate, focused validation on the
reviewed revision. A listed control or existing test is not proof of enforcement.

### Query scope and transactions

- Data values must not become SQL syntax through string interpolation. Dynamic
  identifiers must be resolved or quoted for their actual SQL context; bound
  parameters alone do not protect identifiers. Custom SQL compilation and CLI
  SQL generation deserve the same review as repository queries.
- String ordering, including string entries in `order_by` sequences and sequence
  `default_order_by` values, must respect `allowed_order_columns` and accepted
  directions. Equality selectors must resolve mapped columns and respect
  configured `allowed_filter_columns`. The latter defaults to no additional
  allowlist; consumers exposing field names must configure one. Trusted
  SQLAlchemy ordering expressions are a separate API from the string ordering
  parser.
- `get_or_create` lookups use the same mapped-column resolution and
  `allowed_filter_columns` rules as equality selectors, and apply the default
  soft-delete filter. A matching deleted row is treated as absent; creation is
  attempted, and a conflicting unique constraint can raise `IntegrityError`.
- Many-to-many target lookup fields and link field names must resolve to mapped
  columns, and target lookup fields must not be empty.
- Value-only equality and ID parameters must reject SQLAlchemy expressions.
  This includes `get_by` values, `get_by_id`, soft-delete ID operations, and
  `find_by_ids`.
- Supplied filters and bulk-operation selections must retain their meaning.
  The default filter builder must reject populated, unmapped `FilterParams`
  fields rather than silently dropping them. Value-only bulk-delete IDs must
  not accept SQL expressions as values. Check both repository implementations.
- Operations with default soft-delete filtering must preserve it unless the
  caller explicitly selects the documented deleted-record behavior. Soft delete
  and `include_deleted` are not substitutes for application authorization.
- Supplied `limit` and `offset` must satisfy their type/range checks and the
  configured `max_limit`. An omitted limit is not automatically capped; `find()`
  warns about unbounded retrieval. Resource-exhaustion analysis must account for
  caller limits, collection sizes, parsing depth, and query cost.
- Repositories must preserve transaction ownership: internally owned sessions
  manage commit/rollback; operations using an external session leave that
  transaction's commit/rollback to the caller. Check exceptional and asynchronous
  cancellation paths for leaks or unintended partial persistence.

### Model mutation and output

- `BaseModel.update_from_dict()` requires `allowed_fields` or `updatable_fields`,
  writes only mapped column attributes, and excludes all primary-key attributes,
  `created_at`, `updated_at`, and mapped `deleted_at` even if allowlisted.
  `updatable_fields` is read from the model class, so an instance attribute
  cannot broaden it. `exclude_fields` can narrow the selected allowlist. The
  inherited `BaseModel` constructor rejects these control names and keywords
  that are not mapped model attributes. These are this method's guarantees, not
  automatic protection for direct assignment or every bulk-update API.
- `to_dict()` must always omit `sensitive_fields`, including when those names
  appear in `serializable_fields`. Both `sensitive_fields` and
  `serializable_fields` are read from the model class, so instance attributes
  cannot weaken their restrictions. With no serialization allowlist, other
  mapped columns are returned; consumers must identify their sensitive columns.
- NUL-byte validation on supported ORM and repository bulk-write paths must not
  be accidentally bypassed. It is not general input validation or a guarantee
  for arbitrary SQL executed outside those paths. Review custom-type bind/result
  processing and nested values without assuming stored content is harmless.

### Connections and secret handling

- The effective database destination must match the resolved configuration,
  including explicit URL overrides. `prod` and the normalized `production`
  alias must receive equivalent guards. `EXEC_ENV` is operator input, not proof
  of the real database's purpose; unknown environments currently warn and use
  development naming defaults.
- The current PostgreSQL policy requires TLS for non-local production targets.
  Review URL query overrides, `connect_args`, `host`/`hostaddr`, multiple hosts,
  asynchronous driver adaptation, migration connections, and host client tools
  separately. A permitted override must not silently weaken an applicable
  constraint. Loopback/socket and development defaults may permit plaintext.
- `require` alone is not a guarantee of certificate/hostname verification.
  Preserve explicitly selected `verify-ca`/`verify-full` semantics across driver
  adaptation. Deployments needing authenticated remote peers must choose the
  corresponding verification settings and trust roots.
- Ordinary repr, logs, CLI status, diagnostics, and errors must not unexpectedly
  expose credentials. Include malformed URLs, URL query secrets, exception
  chains, and failing child-process output in review. `safe_db_url()` and secret
  masking are controls to verify, not universal sanitizers.
- SQLAlchemy parameters are hidden by default. Diagnostic capture and explicit
  debug settings need separate assessment: `QueryAnalyzer` retains SQL and
  parameters, and SQL text can itself contain literals. No general redaction
  guarantee extends to every diagnostic artifact or application log.

### Discovery and migrations

- Model discovery and `pre_migration_hook` must enforce the configured package
  boundary before importing a disallowed module. Hook errors must abort the
  command. Mutating the hook's config argument must not redirect the database
  already selected by the shared migration environment.
- Alembic and other operations requiring complete metadata must reject failed
  model imports. The configured-model/empty-metadata guard must not be bypassed
  into a destructive autogenerate result. Display-only discovery has a different
  failure-reporting contract.
- Generated INI values must retain the newline, carriage-return, NUL, leading
  section-marker, and identifier restrictions appropriate to each option.
  Template inputs must come from trusted configuration as specified in
  [AGENTS.md](AGENTS.md); validation does not turn the generator into an
  untrusted-configuration service.
- Runtime migration paths and namespace settings come from `alembic.ini`.
  Namespace-specific operations must respect the selected version table, schema,
  and version files. Sibling version-table exclusions are not permission to hide
  model-table drift from autogenerate or `alembic check`.

### Administrative operations and files

- `db_delete` and the `alembic_reset` CLI must refuse production and require
  their documented confirmation outside production. This CLI guard is not a
  blanket production prohibition on every restore, migration, or Python helper.
  Review each entry point's target selection and confirmation contract.
- Test fixture factories must retain their safety gate: test environment,
  in-memory SQLite, or explicit `allow_destructive=True`. These checks cannot
  prove a URL names disposable data; consumers must select a dedicated database.
- Backup, restore, retention, and migration-file cleanup must act on the intended
  target. Assess path construction, existing files, links, failure cleanup, and
  backup naming against a concrete attacker capability. A failed backup must not
  be presented as a completed recovery artifact.
- Backup files and generated secret files, including temporary and backup copies,
  contain sensitive data. Preserve restrictive permissions where supported and
  verify actual access control on the target OS. POSIX mode bits alone are not
  evidence of equivalent Windows ACL isolation.
- Generated Compose/configuration/initialization content must not allow values
  to inject additional directives or SQL. Published service ports default to
  loopback; LAN exposure requires explicit configuration. Generation must retain
  the missing/placeholder-credential checks for enabled services.
- Existing secret files must not be silently replaced with different credentials.
  Intentional regeneration and credential rotation must preserve their explicit
  execution/overwrite controls and consistent persistent configuration.
- Subprocess argument, environment, stdin, and secret-file channels must preserve
  data boundaries and avoid unintended credential exposure. An argv list by
  itself does not establish safety against the invoked program's option parsing.
  Explicit password CLI flags can expose process arguments; interactive/stdin
  alternatives do not make every subprocess or container channel secret-free.

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

The dependency audit workflow checks known advisories on dependency changes and
weekly. This does not establish that a dependency is safe or audit private/git
dependency source. For `basekit`, the resolved commit in `uv.lock` is the effective
pin while `pyproject.toml` selects a Git branch. Update this policy when public
contracts, dependencies, defaults, or deployment assumptions change. Keep policy
drift and hardening proposals distinct from validated code vulnerabilities.
