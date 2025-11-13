# GitHub Copilot Instructions for repom

## Project Context

This is **repom** - a shared SQLAlchemy foundation package for Python projects.

## Code Style Guidelines

### Imports
- Always use absolute imports: `from repom.base_model import BaseModel`
- Never use old package name `mine_db`

### Database Operations
- Use `BaseRepository` methods instead of raw SQLAlchemy queries
- Always work within transaction contexts using `db_session`

### Testing
- Run tests with: `poetry run pytest tests/unit_tests`
- Use fixtures from `tests/db_test_fixtures.py`
- Test scope: `function` (default), `module`, or `session`

### Configuration
- Use environment variables: `EXEC_ENV` or `PYMINE__CORE__ENV` (dev/test/prod)
- Config class: `MineDbConfig` from `repom.config`
- Database files: `db.dev.sqlite3`, `db.test.sqlite3`, `db.sqlite3`

### Commands
- Always use `poetry run` prefix for commands
- Migration: `poetry run alembic upgrade head`
- DB creation: `poetry run db_create`
- Tests: `poetry run pytest tests/unit_tests`

## VS Code Tasks Available

- `⭐Pytest/unit_tests` - Run unit tests
- `🧪Pytest/all` - Run all tests
- `🤖Poetry/scaffold` - Scaffold new models
- `💾Poetry/db_backup` - Backup database
- `Alembic/migration/all` - Run migrations for all environments

## Common Patterns

### Creating a Model
```python
from repom.base_model import BaseModel
from sqlalchemy import Column, Integer, String

class MyModel(BaseModel):
    __tablename__ = 'my_table'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
```

### Using Repository
```python
from repom.base_repository import BaseRepository

class MyRepository(BaseRepository[MyModel]):
    pass

repo = MyRepository()
item = repo.get_by_id(1)
items = repo.get_by(name="example")
```

## Important Notes

- This is a **shared package** - keep it framework-agnostic
- App-specific models should be in consuming projects
- Always test changes with `poetry run pytest`
- Keep dependencies minimal
