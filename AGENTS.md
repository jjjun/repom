# AGENTS.md - repom Project

## Project Overview

**repom** ships a shared SQLAlchemy foundation (base model, repository, static helpers, and utilities) that applications can extend to suit their own domains. App-specific models and repositories have intentionally been removed from this package.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Build Backend**: hatchling
- **Database ORM**: SQLAlchemy 2.0+
- **Migration Tool**: Alembic
- **Testing Framework**: pytest (unit and behavior tests)
- **Configuration**: python-dotenv for environment management

## Project Structure

```
repom/
├── repom/                      # Main package
│   ├── models/                # Model base classes (BaseModel, BaseModelAuto)
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── repositories/          # Repository implementations (query builder & soft delete mixins)
│   ├── mixins/                # Reusable mixins (SoftDeletableMixin, etc.)
│   ├── scripts/               # CLI scripts (console script entry points)
│   ├── config.py              # Environment-aware configuration
│   ├── database.py            # Database connection setup
│   └── utility.py             # Shared utility functions
├── tests/                     # Test suite for shared functionality
│   ├── unit_tests/           # Unit tests for base components
│   ├── behavior_tests/       # Behavioural notes & examples
│   ├── conftest.py           # Pytest configuration
│   └── db_test_fixtures.py   # Database fixtures for tests
├── alembic/                  # Database migration files
├── data/                     # SQLite databases for each environment
├── docs/                     # Documentation and usage notes
├── pyproject.toml           # uv configuration
├── pytest.ini              # Pytest configuration
└── alembic.ini             # Alembic configuration
```

## Environment Management

Configuration is wired through the `CONFIG_HOOK`, allowing consumers to inject their own settings while the project uses environment-specific databases controlled by the `EXEC_ENV` environment variable (default: `dev`):

- **Production**: `db.sqlite3` (`EXEC_ENV=prod`)
- **Development**: `db.dev.sqlite3` (default, `EXEC_ENV=dev`)
- **Test**: `sqlite:///:memory:` (in-memory) or `db.test.sqlite3` (`EXEC_ENV=test`)

### Setting Environment (Windows PowerShell)
```powershell
$env:EXEC_ENV='dev'  # for development
$env:EXEC_ENV='prod' # for production
```

## Available Commands (Console Scripts)

```bash
# Database management
uv run db_create          # Create database
uv run db_delete          # Delete database
uv run db_sync_master     # Sync master data
uv run db_backup          # Backup database

# Configuration / diagnostics
uv run repom_info          # Show config and loaded models

# Migration commands
uv run alembic revision --autogenerate -m "description"  # Generate migration
uv run alembic upgrade head                              # Apply migrations
```

## Alembic Configuration

### Migration File Location Control

The location of Alembic migration files is controlled **solely** by `alembic.ini`:

- **repom standalone**: `version_locations = alembic/versions`
- **External projects**: `version_locations = %(here)s/alembic/versions`

**Important**: Both file creation (`alembic revision`) and execution (`alembic upgrade`) use the same location specified in `alembic.ini`. This ensures consistency and prevents confusion.

### For External Projects (e.g., mine-py)

**Step 1: Create alembic.ini**

```ini
# mine-py/alembic.ini
[alembic]
script_location = submod/repom/alembic

# CRITICAL: This controls BOTH file creation and execution
# %(here)s refers to the directory containing alembic.ini
version_locations = %(here)s/alembic/versions
```

**Step 2: Set CONFIG_HOOK (optional)**

Only needed if you want to customize other repom features (like model auto-import).

```bash
# .env file
CONFIG_HOOK=mine_py.config:get_repom_config
```

```python
# mine-py/src/mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # Model auto-import settings
        self.model_locations = ['mine_py.models']
        self.allowed_package_prefixes = {'mine_py.', 'repom.'}
        self.model_excluded_dirs = {'base', 'mixin', '__pycache__'}

def get_repom_config():
    return MinePyConfig()
```

**Key Changes from Previous Versions:**

- ❌ **Removed**: `RepomConfig._alembic_versions_path` - no longer exists
- ❌ **Removed**: `env.py` version_locations override - not needed
- ✅ **Simplified**: Single source of truth (`alembic.ini` only)

**Step 3: Define Repository (recommended)**

```python
# mine-py/src/mine_py/repositories/user.py
from repom import BaseRepository
from mine_py.models import User
from sqlalchemy.orm import Session

class UserRepository(BaseRepository[User]):
    pass

# Usage
from repom.database import db_session
repo = UserRepository(session=db_session)
user = repo.get_by_id(1)
```

**メリット**:
- インスタンス化時にモデル名を省略できる
- カスタムメソッドを追加しやすい
- コードが読みやすい

## Testing Framework

### Test Strategy: Transaction Rollback Pattern

repom uses **Transaction Rollback** approach for fast, isolated testing:

**⚠️ Important**: When creating tests, always refer to `docs/guides/testing/testing_guide.md` for detailed guidelines.

**Architecture**:
- `db_engine` (session scope): Creates DB once per test session
- `db_test` (function scope): Provides isolated transaction per test
- Automatic rollback after each test ensures clean state

**Performance**:
- Old approach (DB recreation): ~30s for 195 tests
- Transaction Rollback: ~3s for 195 tests
- **9x speedup achieved**

**Implementation**:
```python
# tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

### Test Structure
- **Unit Tests**: `tests/unit_tests/` - Core functionality tests
- **Behavior Tests**: `tests/behavior_tests/` - Integration scenarios

### Running Tests
```bash
# All tests (195 tests, ~5s)
uv run pytest

# Unit tests only (187 tests, ~3s)
uv run pytest tests/unit_tests

# Behavior tests only (8 tests, ~2s)
uv run pytest tests/behavior_tests

# With verbose output
uv run pytest -v
```

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
- Reuse the fixtures in `tests/db_test_fixtures.py` if you need to validate the shared behaviour.
- When adding new shared utilities, accompany them with tests in `tests/unit_tests/`.

## Key Dependencies

- **sqlalchemy**: ORM and database toolkit
- **alembic**: Database migration management
- **pydantic**: Data validation and serialization
- **python-dotenv**: Environment variable management
- **inflect**: Pluralization utilities
- **pytest**: Testing framework with extensions
- **pytest-sqlalchemy**: SQLAlchemy testing utilities
- **pytest-benchmark**: Performance testing

## Configuration

- **Database Config**: `repom/config.py`
- **Database Connection**: `repom/database.py`
- **Alembic Config**: `alembic.ini` and `alembic/env.py`
- **Test Config**: `pytest.ini` and `tests/conftest.py`

## Notes for AI Assistants

- This project uses **uv** for dependency management — always use `uv run` when executing scripts/tests.
- Tests focus on verifying the shared building blocks; avoid introducing app-specific fixtures here.
- Ensure new shared utilities remain decoupled from any single application domain.
- For model definitions, `get_plural_tablename()` can be used to derive table names from file names to keep them aligned.

## Cross-Project Proposals (AI Agent Rule)

Use issuekit cross-project proposals when work in repom reveals that another project or package must change before the overall goal can be completed.

- `docs/ideas/` is for repom's own feature ideas.
- Issues live in the issuekit API (`project = "repom"`); `docs/issues/incoming/` is the inbox for proposals from other repos.
- Targets include `mine-py`, `fast-domain`, `mine-js-monorepo`, or `py_cr_wrapper`.

To propose a change:
- Send: `issuekit propose --to <repo>` writes into the target repo's `docs/issues/incoming/`.
- Receive: `issuekit incoming` lists inbound proposals; `issuekit adopt <file>` turns one into an API issue.
- See `issuekit protocol` for the full flow and format.

## Issue Management (AI Agent Rule)

Issues live in the issuekit API (`project = "repom"`); there is no local
`docs/issues/{active,completed,indexes}` tracker. The workflow steps are owned by
issuekit (the spec is `docs/issues/README.md`): run `issuekit protocol --role <role>`
or the MCP `get_protocol` tool.

- Inspect: `issuekit info` / `issuekit queue`.
- Author (send): `issuekit author --title "..." --body-file FILE --priority <high|medium|low> --agent <name>`; the API allocates the id (`repom#<id>`). Do not create files or count ids by hand.
- Lifecycle: author -> claim (`claim_next_task` or `issuekit implement <id> --agent <name>`) -> `submit_for_review` -> `approve` / `request_changes`.
- Issue text is English ASCII; files are UTF-8 (no BOM) / LF (pre-commit `issuekit check-encoding`).

## Handoff protocol

This repo uses the issuekit two-agent handoff. For the current steps, run
`issuekit protocol --agent codex` for codex or `issuekit protocol --agent claude`
for claude, or read the issuekit MCP server instructions / `get_protocol` tool.

Do not copy the steps here; issuekit is the source of truth. Launch codex or
Claude Code from the repo root so the MCP server resolves the repo configuration
(the `project` key and API settings).
