# CLAUDE.md - repom Project

## Project Overview

**repom** ships a shared SQLAlchemy foundation (base model, repository, static helpers, and utilities) that applications can extend to suit their own domains. App-specific models and repositories have intentionally been removed from this package.

## Technology Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Build Backend**: hatchling
- **Database ORM**: SQLAlchemy 2.0+
- **Migration Tool**: Alembic
- **Testing Framework**: pytest
- **Configuration**: python-dotenv

## Project Structure

```
repom/
├── repom/                      # Main package
│   ├── models/                # BaseModel, BaseModelAuto
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── repositories/          # Repository implementations
│   ├── mixins/                # SoftDeletableMixin, etc.
│   ├── scripts/               # CLI scripts (console script entry points)
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

Always use `uv run` prefix:

```bash
# Tests
uv run pytest tests/unit_tests      # Unit tests (~3s)
uv run pytest tests/behavior_tests  # Behavior tests (~2s)
uv run pytest                        # All tests (~5s)

# Database
uv run db_create                     # Create DB (dev + prod)
uv run db_delete                     # Delete DB tables
uv run db_backup                     # Backup DB
uv run db_restore                    # Restore DB
uv run db_sync_master               # Sync master data

# PostgreSQL Docker
uv run postgres_generate             # Generate docker-compose.yml
uv run postgres_start                # Start PostgreSQL container
uv run postgres_stop                 # Stop PostgreSQL container

# Migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# Diagnostics
uv run repom_info                    # Show config and loaded models
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

## Docker Auto-Start (PostgreSQL / Redis)

`db_type == 'postgres'` の場合、以下のスクリプトはコンテナ未起動時に自動起動します:
- `db_create` / `db_delete` / `db_sync_master`

共通エントリポイント:

- `repom.postgres.manage.ensure_running(*, timeout_seconds=30, include_pgadmin=True)`
  - postgres と (`config.pgadmin.container.enabled` が True かつ `include_pgadmin=True` なら) pgAdmin の双方を保証する
  - 失敗時は `RuntimeError` を投げる (CLI からは traceback、fast-domain lifespan からは捕捉)
- `repom.redis.manage.ensure_running(*, timeout_seconds=30)`
  - Redis コンテナのみを保証する
  - 失敗時は `RuntimeError`

`timeout_seconds` は `DockerManager.start(timeout_seconds=...)` 経由で
`wait_for_service(max_retries=...)` に伝搬する。fast-domain のように
lifespan 設定値で readiness 待機を制御したい場合に使う。

## Documentation Structure

```
docs/
├── guides/         # 使い方ガイド（testing, repository, model など）
├── ideas/          # 機能提案
├── technical/      # 実装詳細・制約の調査
└── issues/
    ├── README.md   # 規約 (issuekit が参照)
    ├── indexes/    # 生成インデックス（手編集しない）
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

ローカル issue は `issuekit` CLI で管理する (規約は `docs/issues/README.md`)。

- 状態確認・次の id: `issuekit info` (VS Code タスク `issue: info` でも可)
- issue 変更後: `issuekit generate-indexes` と `issuekit validate`
- 完了時: `issuekit complete <id> --summary "..." --verification "..."`
- issue ファイルは英語 ASCII のみ。`docs/issues/indexes/` は生成物（手編集しない）。README に完了 issue 表を書き戻さない。
- ファイルは UTF-8 (BOM なし) / LF。pre-commit (`issuekit check-encoding`) が検査する。

完了トリガーワード: 「完了」「終わった」「解決しました」「done」「complete」

## Cross-Project Proposals

repom 側だけでは完結できず、外部プロジェクト・外部パッケージ側の変更が必要な場合は issuekit のクロスプロジェクト提案を使う。

- 送信: `issuekit propose --to <repo>` で対象リポジトリの `docs/issues/incoming/` に提案を送る
- 受信: `issuekit incoming` で確認し、採用するなら `issuekit adopt <file>` で `docs/issues/active/` の issue にする
- 手順とフォーマットは `issuekit protocol` を参照する

`docs/ideas/` は repom 内の機能アイデア、`docs/issues/` は repom 内の実装タスクに使う。

## Development Guidelines

- Keep this package **framework-agnostic** — no app-specific logic here
- Add app-specific models/repositories in the consuming project
- Accompany new shared utilities with tests in `tests/unit_tests/`
- Use `get_plural_tablename()` to derive table names from file names

## Handoff protocol

This repo uses the issuekit two-agent handoff. For the current steps, run
`issuekit protocol --agent codex` for codex or `issuekit protocol --agent claude`
for claude, or read the issuekit MCP server instructions / `get_protocol` tool.

Do not copy the steps here; issuekit is the source of truth. Launch codex or
Claude Code from the repo root so the MCP server resolves the correct
`docs/issues/` directory.
