# CLAUDE.md - repom Project

## Project Overview

**repom** ships a shared SQLAlchemy foundation (base model, repository, static helpers, and utilities) that applications can extend to suit their own domains. App-specific models and repositories have intentionally been removed from this package.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: Poetry
- **Database ORM**: SQLAlchemy 2.0+
- **Migration Tool**: Alembic
- **Testing Framework**: pytest
- **Configuration**: python-dotenv

## Project Structure

```
repom/
├── repom/                      # Main package
│   ├── models/                # BaseModel, BaseModelAuto, BaseStaticModel
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── repositories/          # Repository implementations
│   ├── mixins/                # SoftDeletableMixin, etc.
│   ├── scripts/               # CLI scripts (Poetry entry points)
│   ├── postgres/              # PostgreSQL Docker management
│   ├── redis/                 # Redis Docker management
│   ├── config.py              # Environment-aware configuration
│   ├── database.py            # Database connection setup
│   └── utility.py             # Shared utility functions
├── tests/
│   ├── unit_tests/            # Core functionality tests
│   ├── behavior_tests/        # Integration scenarios
│   ├── conftest.py
│   └── db_test_fixtures.py
├── alembic/                   # Migration files
├── data/                      # SQLite databases per environment
├── docs/                      # Documentation
├── pyproject.toml
└── alembic.ini
```

## Commands

Always use `poetry run` prefix:

```bash
# Tests
poetry run pytest tests/unit_tests      # Unit tests (~3s)
poetry run pytest tests/behavior_tests  # Behavior tests (~2s)
poetry run pytest                        # All tests (~5s)

# Database
poetry run db_create                     # Create DB (dev + prod)
poetry run db_delete                     # Delete DB tables
poetry run db_backup                     # Backup DB
poetry run db_restore                    # Restore DB
poetry run db_sync_master               # Sync master data

# PostgreSQL Docker
poetry run postgres_generate             # Generate docker-compose.yml
poetry run postgres_start                # Start PostgreSQL container
poetry run postgres_stop                 # Stop PostgreSQL container

# Migrations
poetry run alembic revision --autogenerate -m "description"
poetry run alembic upgrade head

# Diagnostics
poetry run repom_info                    # Show config and loaded models
```

## Environment Variables

```bash
EXEC_ENV=dev    # Development (default)
EXEC_ENV=test   # Test (uses in-memory SQLite)
EXEC_ENV=prod   # Production
```

PowerShell での設定:
```powershell
$env:EXEC_ENV='dev'
```

## Code Style

### Imports
- Always use absolute imports: `from repom.models import BaseModel`
- Never use old package name `mine_db`

### Model Definition
```python
from repom.models import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

class MyModel(BaseModel):
    __tablename__ = 'my_table'
    # id is auto-added by BaseModel (use_id=True by default)
    name: Mapped[str] = mapped_column(String(100))
```

### Repository Pattern
```python
from repom import BaseRepository

class MyRepository(BaseRepository[MyModel]):
    pass

repo = MyRepository(session=db_session)
item = repo.get_by_id(1)
items = repo.get_by(name="example")
```

### Database Operations
- Use `BaseRepository` methods instead of raw SQLAlchemy queries
- Always work within transaction contexts using `db_session`

## Testing

Transaction Rollback パターン（9倍高速化）:

```python
# tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

- `db_engine`: session scope — DB を一度だけ作成
- `db_test`: function scope — テストごとにトランザクションをロールバック

**重要**: テスト作成前に必ず `docs/guides/testing/testing_guide.md` を参照。

## Configuration (CONFIG_HOOK)

外部プロジェクトからカスタマイズする場合:

```python
# .env
CONFIG_HOOK=mine_py.config:get_repom_config
```

```python
# mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        self.model_locations = ['mine_py.models']
        self.allowed_package_prefixes = {'mine_py.', 'repom.'}
        self.db_type = 'postgres'  # PostgreSQL を使う場合

def get_repom_config():
    return MinePyConfig()
```

## Alembic

Migration file location は `alembic.ini` のみで制御:

```ini
# repom standalone
version_locations = alembic/versions

# External projects
version_locations = %(here)s/alembic/versions
```

## PostgreSQL Auto-Start

`db_type == 'postgres'` の場合、以下のスクリプトはコンテナ未起動時に自動起動します:
- `db_create` / `db_delete` / `db_sync_master`

共通関数: `repom.postgres.manage.ensure_running()`

## Documentation Structure

```
docs/
├── guides/         # 使い方ガイド（testing, repository, model など）
├── ideas/          # 機能提案
├── technical/      # 実装詳細・制約の調査
└── issue/
    ├── README.md   # Issue インデックス（必ず更新）
    ├── active/     # 対応中の Issue
    └── completed/  # 完了済み Issue（NNN_name.md）
```

### 重要ガイド

| 機能 | ガイドファイル |
|---|---|
| テスト | `docs/guides/testing/testing_guide.md` |
| BaseModelAuto / スキーマ生成 | `docs/guides/model/base_model_auto_guide.md` |
| BaseRepository | `docs/guides/repository/base_repository_guide.md` |
| FilterParams | `docs/guides/repository/repository_filter_params_guide.md` |
| Eager Loading | `docs/guides/repository/repository_advanced_guide.md` |
| モデル自動インポート | `docs/guides/features/auto_import_models_guide.md` |

## Issue Management

Issue が完了したら:
1. `docs/issue/active/XXX_name.md` → `docs/issue/completed/NNN_name.md` に移動（連番付与）
2. `docs/issue/README.md` を更新（active から completed セクションへ移動）
3. コミット: `docs(issue): Complete issue #NNN - [title]`

完了トリガーワード: 「完了」「終わった」「解決しました」「done」「complete」

## Development Guidelines

- Keep this package **framework-agnostic** — no app-specific logic here
- Add app-specific models/repositories in the consuming project
- Accompany new shared utilities with tests in `tests/unit_tests/`
- Use `get_plural_tablename()` to derive table names from file names
