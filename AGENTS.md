# AGENTS.md - repom Project

## Project Overview

**repom** ships a shared SQLAlchemy foundation (base model, repository, static helpers, and utilities) that applications can extend to suit their own domains. App-specific models and repositories have intentionally been removed from this package.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Database ORM**: SQLAlchemy 2.0+
- **Migration Tool**: Alembic
- **Testing Framework**: pytest (unit and behavior tests)
- **Configuration**: python-dotenv for environment management

## Project Structure

```
repom/
├── repom/                      # Main package
│   ├── models/                # Model base classes (BaseModel, BaseModelAuto, BaseStaticModel)
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── repositories/          # Repository implementations (query builder & soft delete mixins)
│   ├── mixins/                # Reusable mixins (SoftDeletableMixin, etc.)
│   ├── scripts/               # CLI scripts (Poetry entry points)
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
├── pyproject.toml           # Poetry configuration
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

## Available Commands (Poetry Scripts)

```bash
# Database management
poetry run db_create_master    # Create master database
poetry run db_create          # Create database
poetry run db_delete          # Delete database
poetry run db_backup          # Backup database

# Configuration / diagnostics
poetry run repom_info          # Show config and loaded models

# Migration commands
poetry run alembic revision --autogenerate -m "description"  # Generate migration
poetry run alembic upgrade head                              # Apply migrations
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
poetry run pytest

# Unit tests only (187 tests, ~3s)
poetry run pytest tests/unit_tests

# Behavior tests only (8 tests, ~2s)
poetry run pytest tests/behavior_tests

# With verbose output
poetry run pytest -v
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

- This project uses **Poetry** for dependency management — always use `poetry run` when executing scripts/tests.
- Tests focus on verifying the shared building blocks; avoid introducing app-specific fixtures here.
- Ensure new shared utilities remain decoupled from any single application domain.
- For model definitions, `get_plural_tablename()` can be used to derive table names from file names to keep them aligned.
