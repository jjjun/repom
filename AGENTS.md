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
- **Testing Framework**: pytest (unit and behavior tests)
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
│   ├── behavior_tests/       # Behavioural notes & examples
│   ├── integration_tests/    # External-project and database integration tests
│   ├── conftest.py           # Pytest configuration
├── alembic/                  # Shared migration environment referenced via script_location; versions/ holds repom's own migrations
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

`alembic.ini` is trusted configuration, equivalent to source code:
`pre_migration_hook` is a code-execution setting, and the shared `env.py`
resolves and calls whatever it names with exceptions left uncaught.
`AlembicTemplates.generate_alembic_ini` (and `AlembicSetup.create_alembic_ini`,
which wraps it) must never be fed a value derived from untrusted input - a
project name, a CI variable, anything an attacker could influence - for
`script_location`, `version_locations`, `version_table`,
`version_table_schema`, or `autogenerate_exclude_tables`. Every interpolated
value is validated to reject a newline, a carriage return, a NUL byte, and a
leading `[`; `version_table`, `version_table_schema`, and each
`autogenerate_exclude_tables` entry must additionally match a plain
identifier pattern (`[A-Za-z_][A-Za-z0-9_]*`).

### For External Projects (e.g., mine-py)

**Step 1: Create alembic.ini**

```ini
# mine-py/alembic.ini
[alembic]
script_location = submod/repom/alembic

# CRITICAL: This controls BOTH file creation and execution
# %(here)s refers to the directory containing alembic.ini
version_locations = %(here)s/alembic/versions

# Optional: isolate an independent migration namespace.
# Defaults to alembic_version when omitted.
# version_table = alembic_version_fast_domain

# Optional: place the version table in a named schema.
# Defaults to no explicit schema when omitted.
# version_table_schema = migration_fast_domain

# Comma-separated sibling migration version tables to ignore during autogenerate.
# Do not list the active version_table; Alembic excludes it automatically.
# autogenerate_exclude_tables = alembic_version_fast_domain

# Optional: validate the resolved database before Alembic runs.
# The callable signature is validate_alembic_database(db_config).
# pre_migration_hook = mine_py.alembic_runtime:validate_alembic_database
```

**Step 2: Configure the consuming project (required)**

Set `CONFIG_HOOK` to a consumer-owned hook. This is required for Alembic
autogenerate: `RepomConfig.model_locations` defaults to an empty list, so no
consumer models are loaded unless the hook sets it. Without model locations,
the empty-metadata guard cannot protect the live database from a migration
that drops every table. Set `root_path` as well so database and data paths
resolve under the consumer project rather than the repom checkout. Set a
project-specific `db_name` when using file-based SQLite or when distinct
PostgreSQL database names are needed.

```bash
# .env file
CONFIG_HOOK=mine_py.config:get_repom_config
```

```python
# mine-py/src/mine_py/config.py
from pathlib import Path


def get_repom_config(config):
    config.root_path = str(Path(__file__).resolve().parents[2])
    config.db_name = "mine_py"
    config.model_locations = ['mine_py.models']
    config.allowed_package_prefixes = {'mine_py.', 'repom.'}
    config.model_excluded_dirs = {'base', 'mixin', '__pycache__'}
    return config
```

**Step 3: Define Repository (recommended)**

```python
# mine-py/src/mine_py/repositories/user.py
from repom import BaseRepository
from mine_py.models import User
from sqlalchemy.orm import Session

class UserRepository(BaseRepository[User]):
    pass

# Usage in an application-owned transaction
from repom.database import get_reusable_sync_transaction

with get_reusable_sync_transaction() as session:
    repo = UserRepository(session=session)
    user = repo.get_by_id(1)
```

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
- **Behavior Tests**: `tests/behavior_tests/` - Integration scenarios
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
configured `addopts` include `-x` (stop after the first failure) and
`--benchmark-skip`. Default runs capture successful test output and keep
logging concise. Use the verbose command above when detailed stdout and DEBUG
logs are needed.

### For External Projects

External projects (e.g., mine-py) can use the same helper:

```python
# external_project/tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures(
    db_url="sqlite:///:memory:",  # Optional
    model_loader=my_loader          # Optional
)
```

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
`issuekit protocol --agent <agent>` (e.g. `codex`, `claude`, or `kimi`) or
`issuekit protocol --role <role>` (e.g. `implementer` or `reviewer`), or read the
issuekit MCP server instructions / `get_protocol` tool.

Do not copy the steps here; issuekit is the source of truth. Launch your agent from the repo root so the MCP server resolves the repo configuration
(the `project` key and API settings).

If work originates in another project but belongs here, use the cross-project
proposal flow from the origin project. Do not create a local issue here unless
the protocol says the work is local to this repo.
