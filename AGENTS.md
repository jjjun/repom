# AGENTS.md - repom Project

## Project Overview

**repom** ships a shared SQLAlchemy foundation (base model, repository, static helpers, and utilities) that applications can extend to suit their own domains. App-specific models and repositories have intentionally been removed from this package.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Database ORM**: SQLAlchemy 2.0+
- **Migration Tool**: Alembic
- **Testing Framework**: pytest (unit and behaviour tests)
- **Configuration**: python-dotenv for environment management

## Project Structure

```
repom/
├── repom/                      # Main package
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── scripts/               # CLI scripts (Poetry entry points)
│   ├── base_model.py          # Base SQLAlchemy model helpers
│   ├── base_repository.py     # Base repository abstraction（提供メソッドを通じてモデルの取得や操作を行います）
│   ├── base_static.py         # Base static model class
│   ├── config.py              # Environment-aware configuration
│   ├── db.py                  # Database connection setup
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

Configuration is wired through the `CONFIG_HOOK`, allowing consumers to inject their own settings while the project uses environment-specific databases controlled by the `EXEC_ENV` environment variable:

- **Production**: `db.sqlite3` (default)
- **Development**: `db.dev.sqlite3` (`EXEC_ENV=dev`)
- **Test**: `db.test.sqlite3` (`EXEC_ENV=test`)

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
from repom.config import MineDbConfig

class MinePyConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        # Customize other settings here (model_locations, etc.)

def get_repom_config():
    return MinePyConfig()
```

**Key Changes from Previous Versions:**

- ❌ **Removed**: `MineDbConfig._alembic_versions_path` - no longer exists
- ❌ **Removed**: `env.py` version_locations override - not needed
- ✅ **Simplified**: Single source of truth (`alembic.ini` only)

## Testing Framework

### Test Structure
- **Unit Tests**: `tests/unit_tests/`
- **Behavior Tests**: `tests/behavior_tests/`

### Running Tests
```bash
# All shared tests (from the repository root)
poetry run pytest tests/unit_tests

# Specific directories
poetry run pytest tests/behavior_tests
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
- **Database Connection**: `repom/db.py`
- **Alembic Config**: `alembic.ini` and `alembic/env.py`
- **Test Config**: `pytest.ini` and `tests/conftest.py`

## Notes for AI Assistants

- This project uses **Poetry** for dependency management — always use `poetry run` when executing scripts/tests.
- Tests focus on verifying the shared building blocks; avoid introducing app-specific fixtures here.
- Ensure new shared utilities remain decoupled from any single application domain.
