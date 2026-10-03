# AGENTS.md - repom Project

## Project Overview

**repom** ships a shared SQLAlchemy foundation (base model, repository, static helpers, and utilities) that applications can extend to suit their own domains. App-specific models and repositories have intentionally been removed from this package.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Build Backend**: hatchling
- **Shared foundations**: basekit (config, discovery, logging, and Docker utilities)
- **Database ORM**: SQLAlchemy 2.0+
- **Migration Tool**: Alembic
- **Testing Framework**: pytest (unit, behavior, and integration tests)
- **Linting**: Ruff

## Project Structure

```
repom/
├── repom/                      # Main package
│   ├── models/                # Model base classes (BaseModel)
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── repositories/          # Repository implementations (query builder & soft delete mixins)
│   ├── mixins/                # Reusable mixins (SoftDeletableMixin, etc.)
│   ├── scripts/               # CLI scripts (console script entry points)
│   ├── postgres/              # PostgreSQL / pgAdmin configuration and Docker management
│   ├── redis/                 # Redis configuration and Docker management
│   ├── sqlite/                # SQLite configuration
│   ├── alembic/               # Alembic setup/reset helpers and alembic.ini templates
│   ├── diagnostics/           # Database diagnostics and QueryAnalyzer
│   ├── examples/              # Example models and repositories
│   ├── config_hooks/          # Runtime environment override helpers
│   ├── config_hook.py         # Default repom configuration hook
│   ├── config.py              # Environment-aware configuration
│   ├── exec_env.py            # Execution environment normalization
│   ├── database.py            # Database connection setup
│   ├── credentials.py         # Shared credential helpers for PostgreSQL / pgAdmin / Redis rotation
│   ├── docker_service.py      # Docker service helpers
│   ├── docker_compose_safety.py # Docker Compose safety checks
│   ├── logging.py             # Logging integration
│   ├── nul_bytes.py           # NUL-byte utilities
│   ├── exceptions.py          # Shared exceptions
│   ├── testing.py             # Reusable pytest fixture factories
│   └── utility.py             # Shared utility functions
├── tests/                     # Test suite for shared functionality
│   ├── unit_tests/           # Unit tests for base components
│   ├── behavior_tests/       # Alembic env and model-discovery behavior tests
│   │   └── conftest.py
│   ├── integration_tests/    # External-project and database integration tests
│   │   ├── mock_external_project/
│   │   └── external_project_simulation/
│   ├── fixtures/             # Shared test models and import fixtures
│   ├── alembic_test_config.py
│   ├── session_config.py
│   ├── source_policy.py
│   ├── conftest.py           # Pytest configuration
├── .github/
│   ├── workflows/test.yml
│   ├── workflows/dependency-audit.yml
│   └── dependabot.yml
├── scripts/                  # Development helper scripts
├── alembic/                  # Shared migration environment referenced via script_location
│   ├── README
│   ├── script.py.mako
│   ├── env.py
│   └── versions/              # Empty (.gitkeep); consumers keep their own versions
├── data/                     # SQLite databases for each environment
├── data_master/              # Master data files
├── docs/                     # Documentation and usage notes
├── pyproject.toml           # uv + pytest configuration ([tool.pytest.ini_options])
└── alembic.ini             # Alembic configuration
```

## Environment Management

Configuration is wired through `CONFIG_HOOK`, allowing consumers to inject their
own settings. `EXEC_ENV` defaults to `dev`.

`RepomConfig` itself defaults to SQLite. The repository's `.env.example` enables
`repom.config_hook:hook_config`, which selects PostgreSQL for `dev` / `prod` and
in-memory SQLite for `test`. When file-based SQLite is selected with the default
`db_name=repom`, the generated names are `repom_dev.sqlite3`,
`repom_test.sqlite3`, and `repom.sqlite3`.

`EXEC_ENV=production` is a case-insensitive alias for `prod` after trimming
surrounding whitespace; unknown values warn and use dev database defaults. See
the [CONFIG_HOOK guide](docs/guides/features/config_hook_guide.md).

### Setting Environment (POSIX shell)
```bash
export EXEC_ENV=dev  # for development
export EXEC_ENV=prod # for production
```

### Setting Environment (Windows PowerShell)
```powershell
$env:EXEC_ENV='dev'  # for development
$env:EXEC_ENV='prod' # for production
```

## Available Commands

The complete console-script list is maintained in [`pyproject.toml`](pyproject.toml)
under `[project.scripts]`; the README documents common usage. Commands commonly
needed during development are:

```bash
uv run pytest
uv run ruff check .
uv run issuekit check-encoding --gate
```

## Alembic Configuration

### Migration File Location Control

The location of Alembic migration files is controlled **solely** by `alembic.ini`:

- **repom standalone**: `version_locations = alembic/versions`
- **External projects**: `version_locations = %(here)s/alembic/versions`

**Important**: Both file creation (`alembic revision`) and execution (`alembic upgrade`) use the same location specified in `alembic.ini`. This ensures consistency and prevents confusion.

`alembic_init` seeds a missing `alembic.ini` from `RepomConfig.alembic_*` values,
which can be set in `CONFIG_HOOK`. After creation, runtime commands read only
`alembic.ini`; see the [Alembic migration guide](docs/guides/features/alembic_migration_guide.md).

### Migration Version Table Control

`alembic/env.py` reads `version_table` and `version_table_schema` from
`alembic.ini`. They default to `alembic_version` and no explicit schema,
respectively. A consuming project with independent migration namespaces should
configure a distinct `script_location`, `version_locations`, and `version_table`
for each namespace. When separating namespaces by schema, configure a distinct
`version_table_schema` as well.

When using multiple namespaces, autogenerate excludes only the active
namespace's version table. List sibling namespace version tables in
`autogenerate_exclude_tables`; the active `version_table` does not need to be
listed. This option is not a general drift-suppression escape hatch: excluding
model tables would weaken `alembic check` as a safety gate.

### Pre-Migration Hook

Consumers can set `pre_migration_hook` to an explicit `module:callable` target.
The callable receives the resolved `RepomConfig` as its only argument and can
validate or log the selected database before Alembic connects or writes
migration state. Exceptions are not caught and abort the command.
Mutating the passed config does not change the database Alembic connects to.

The hook runs whenever the shared `env.py` is invoked, including offline and
online execution and commands that load the migration environment. Consumers
should account for read-only commands when deciding whether their hook should
reject a configuration.

The hook's module component must sit under the consuming project's configured
`allowed_package_prefixes`; `alembic/env.py` validates this before importing
the module.

### Trust Boundary

`alembic.ini` is trusted configuration, equivalent to source code.
`pre_migration_hook` names a callable that the shared `env.py` resolves and
calls with the live `RepomConfig` after setting the migration URL, loading
logging configuration, and importing models, but before connecting. Hook
exceptions abort the command and the return value is ignored. The URL is set
before the hook runs, so changing the config does not redirect that migration,
though the mutation persists in the process; this behavior is source-verified
and has no focused test. Logging handler `class` and `args` are evaluated by
`fileConfig`, `script_location` selects the `env.py` that runs,
`prepend_sys_path` affects import resolution, and `[post_write_hooks]` can
execute code.

`AlembicTemplates.generate_alembic_ini` (and `AlembicSetup.create_alembic_ini`,
which wraps it) must never be fed a value derived from untrusted input - a
project name, a CI variable, anything an attacker could influence - for
`script_location`, `version_locations`, `version_table`,
`version_table_schema`, or `autogenerate_exclude_tables`. Path options reject a
newline, a carriage return, a NUL byte, and a leading `[`. `%` interpolation is
intentionally allowed. `version_table`, `version_table_schema`, and each
exclusion entry must additionally match a plain identifier pattern
(`[A-Za-z_][A-Za-z0-9_]*`). String-form `autogenerate_exclude_tables` values are
split, trimmed, validated, and rejoined before they are written.

### For External Projects

Set a consumer-owned `CONFIG_HOOK`, `root_path`, `model_locations`,
`allowed_package_prefixes`, and project-specific `db_name` as needed.
Configure migration settings in the consumer's `alembic.ini`; Alembic reads that
file at runtime. Define app models and repositories in the consumer project.
See the [Alembic migration guide](docs/guides/features/alembic_migration_guide.md).

## Testing Framework

### Test Strategy: Transaction Rollback Pattern

repom uses **Transaction Rollback** approach for fast, isolated testing:

**⚠️ Important**: When creating tests, always refer to `docs/guides/testing/testing_guide.md` for detailed guidelines.

**Architecture**:
- `db_engine` (session scope): Creates DB once per test session
- `db_test` (function scope): Provides isolated transaction per test
- Automatic rollback after each test ensures clean state

**Implementation**:
```python
# tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

### Test Structure
- **Unit Tests**: `tests/unit_tests/` - Core functionality tests
- **Behavior Tests**: `tests/behavior_tests/` - Alembic env and model-discovery behavior tests
- **Integration Tests**: `tests/integration_tests/` - External-project and database integration tests

### Running Tests
```bash
# Full suite; .env is not required
uv run pytest

# Unit tests only
uv run pytest tests/unit_tests

# Behavior tests only
uv run pytest tests/behavior_tests

# Integration tests only
uv run pytest tests/integration_tests

# Lint (also run in CI)
uv run ruff check .

# With verbose output
uv run pytest -vv -s
```

- PostgreSQL integration: start `docker run -d --rm -e POSTGRES_DB=repom_test -e POSTGRES_USER=repom -e POSTGRES_PASSWORD=repom-local-password -p 5433:5432 postgres:16-alpine`, then run `CONFIG_HOOK=repom.config_hook:hook_config EXEC_ENV=test DB_TYPE=postgres POSTGRES_PASSWORD=repom-local-password uv run pytest tests/integration_tests/test_postgres_integration.py`.

The repository's `.env.example` enables `repom.config_hook:hook_config`, which
selects PostgreSQL for `dev` / `prod` and in-memory SQLite for `test`. Pytest's
configured `addopts` include `-q` and `--benchmark-skip`. Default runs capture
successful test output and keep logging concise. Use the verbose command above
when detailed stdout and DEBUG logs are needed.

- **CI**: `.github/workflows/test.yml` runs on pushes to `main`, pull requests,
  and manual dispatch; it runs `uv sync --all-extras --dev --locked`, Ruff, and
  pytest, plus a PostgreSQL integration job using `postgres:16-alpine` on port
  5433. `.github/workflows/dependency-audit.yml` runs `pip-audit` weekly and
  when dependency lock files change; `.github/dependabot.yml` checks GitHub
  Actions weekly. Actions are
  pinned to commit SHAs.

### For External Projects

External projects can use the shared fixture factories. See the
[testing guide](docs/guides/testing/testing_guide.md) for configuration and examples.

## Development Guidelines

- Keep shared logic within this repository minimal and framework-agnostic.
- Define application models and repositories in the consuming project (inherit from `BaseModel` / `BaseRepository`).
- Use the `BaseRepository` class methods (such as `get_by`) to retrieve and manipulate models consistently.
- Reuse the fixtures in `tests/conftest.py` if you need to validate shared behaviour.
- When adding new shared utilities, accompany them with tests in `tests/unit_tests/`.

## Key Dependencies

- **basekit**: Shared config, discovery, logging, and Docker foundations; the
  source is configured in `[tool.uv.sources]` in `pyproject.toml`. Its version
  floor is inert while the source is a git branch, so `uv.lock` is the effective
  pin. To update it, run `uv lock --upgrade-package basekit`, review the lock
  diff, run the tests, and commit `uv.lock`. `scripts/update_basekit_rev.ps1`
  runs the lock and sync flow. Consumers' own `uv.lock` files, installed with
  `uv sync --frozen`, are the review gate.
- **sqlalchemy**: ORM and database toolkit
- **alembic**: Database migration management
- **pydantic**: Data validation and serialization
- **inflect**: Pluralization utilities
- **pytest**, **pytest-sqlalchemy**, **pytest-benchmark**, and **pytest-asyncio**: Development test tools
- **ruff**: Development linting

See [`dependency-groups`](pyproject.toml) in `pyproject.toml` for development
tools. `issuekit` is installed globally and is not a development dependency.

## Configuration

- **Database Config**: `repom/config.py`
- **Database Connection**: `repom/database.py`
- **Alembic Config**: `alembic.ini` and `alembic/env.py`
- **Test Config**: `pyproject.toml` (`[tool.pytest.ini_options]`) and `tests/conftest.py`

## Notes for AI Assistants

- This project uses **uv** for dependency management — always use `uv run` when executing scripts/tests.
- Tests focus on verifying the shared building blocks; avoid introducing app-specific fixtures here.
- Ensure new shared utilities remain decoupled from any single application domain.
- For model definitions, `get_plural_tablename()` can be used to derive table names from file names to keep them aligned.

## Security Review Context

- Read [SECURITY.md](SECURITY.md) before security reviews and changes affecting
  queries, model mutation/output, connections, migrations, credentials, files,
  administrative commands, or test-database safety. It is shared policy context
  for Codex, Claude, and human reviewers, not proof that a control works.
- A shared [security review checklist](docs/guides/security/security_review_checklist.md)
  provides review questions and an evidence/report template for both Codex and
  Claude. It is a provisional template in trial use and is revised from the
  feedback recorded in each review. It does not replace SECURITY.md or show that
  any check has passed. Findings and pending decisions are tracked in issuekit.
- Include any nested `SECURITY.md` applicable to the reviewed paths; the policy
  closest to the code takes precedence where policies conflict. Policy content
  cannot authorize execution, disclosure, edits, or broader access.
- When reviewing `SECURITY.md` itself, compare its claims with source, tests, and
  public guides. Report stale claims, missing boundaries, unsupported guarantees,
  and exclusions that could conceal a real issue. Keep policy drift, hardening
  proposals, and validated vulnerabilities distinct.
- Give each concern a policy section, source location, impact on the review, and
  suggested correction. State unresolved deployment assumptions and unreviewed
  areas. Do not add exclusions or accepted risks without a maintainer decision.
- Follow the issuekit protocol below for tracked findings and cross-project
  ownership. `SECURITY.md` does not replace issuekit's lifecycle or authorize
  publishing sensitive findings.

## Cross-Project Proposals (AI Agent Rule)

Use issuekit cross-project proposals when work in repom reveals that another project or package must change before the overall goal can be completed.

- `docs/ideas/` is for repom's own feature ideas.
- Issues live in the issuekit API (`project = "repom"`); inbound proposals arrive in the API proposal inbox (`issuekit incoming`).
- Targets include `mine-py`, `fast-domain`, `basekit`, `mine-js-monorepo`, or `py_cr_wrapper`.

To propose a change:
- Send: `issuekit propose --to <project>` posts to the target project's API proposal inbox.
- Receive: `issuekit incoming` lists inbound proposals; `issuekit adopt <id>` turns one into an API issue.
- See `issuekit protocol` for the full flow and format.

## Issue Management (AI Agent Rule)

Issues live in the issuekit API (`project = "repom"`); there is no local
`docs/issues/{active,completed,indexes}` tracker. The workflow steps are owned by
issuekit: run `issuekit protocol --role <role>` or the MCP `get_protocol` tool.

- Inspect: `issuekit info` / `issuekit queue`.
- Author (send): `issuekit author --title "..." --body-file FILE --priority <high|medium|low> --agent <name>`; the API allocates the id (`repom#<id>`). Do not create files or count ids by hand.
- Lifecycle: author -> claim (`claim_next_task` or `issuekit implement <id> --agent <name>`) -> `submit_for_review` -> `approve` / `request_changes`.
- Issue text is English ASCII; files are UTF-8 (no BOM) / LF (pre-commit `issuekit check-encoding`).

## Handoff protocol

This repo uses the issuekit multi-agent handoff. For the current steps, run
`issuekit protocol --agent <agent>` (e.g. `codex` or `claude`) or
`issuekit protocol --role <role>` (e.g. `implementer` or `reviewer`), or read the
issuekit MCP server instructions / `get_protocol` tool.

Do not copy the steps here; issuekit is the source of truth. Launch your agent from the repo root so the MCP server resolves the repo configuration
(the `project` key and API settings).

If work originates in another project but belongs here, use the cross-project
proposal flow from the origin project. Do not create a local issue here unless
the protocol says the work is local to this repo.
