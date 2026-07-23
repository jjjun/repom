# repom

`repom` は、アプリケーションから拡張できる SQLAlchemy 2.x の共通基盤です。
モデル基底、同期・非同期 Repository、設定フック、Alembic 補助、テスト
fixture、PostgreSQL/Redis の Docker 管理を提供します。アプリ固有のモデルや
Repository は利用側のプロジェクトに置いてください。

## 必要環境

- Python 3.12 以上
- [uv](https://docs.astral.sh/uv/)

```bash
git clone <repository-url> repom
cd repom
uv sync
uv run pytest
```

任意機能は必要なものだけ追加します。

```bash
uv sync --extra postgres        # psycopg
uv sync --extra postgres-async  # asyncpg
uv sync --extra redis
uv sync --extra async           # aiosqlite
uv sync --extra async-all       # aiosqlite + asyncpg
```

## 基本的な使い方

### モデル

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseModelAuto


class Task(BaseModelAuto, use_id=True, use_created_at=True, use_updated_at=True):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        info={"description": "Task title"},
    )
```

`BaseModelAuto` は `get_create_schema()`、`get_update_schema()`、
`get_response_schema()` を提供します。詳細は
[BaseModelAuto ガイド](docs/guides/model/base_model_auto_guide.md)を参照してください。

### Repository

```python
from repom import BaseRepository


class TaskRepository(BaseRepository[Task]):
    pass
```

アプリケーションが所有するトランザクションでは、セッションを明示します。
外部セッション使用時の `save()` は `flush()` まで行い、commit は呼び出し側が
担当します。

```python
from repom.database import get_reusable_sync_transaction

with get_reusable_sync_transaction() as session:
    repo = TaskRepository(session=session)
    task = repo.save(Task(title="Write documentation"))
    same_task = repo.get_by_id(task.id)
```

短い単発操作ではセッションを省略できます。この場合は Repository が内部
セッションを作成し、書き込みを commit します。

```python
task = TaskRepository().save(Task(title="One operation"))
```

詳細は [BaseRepository ガイド](docs/guides/repository/base_repository_guide.md)と
[セッション管理ガイド](docs/guides/repository/repository_session_patterns.md)を
参照してください。

### 非同期 Repository

```python
from repom import AsyncBaseRepository
from repom.database import get_standalone_async_transaction


class AsyncTaskRepository(AsyncBaseRepository[Task]):
    pass


async def load_task(task_id: int):
    async with get_standalone_async_transaction() as session:
        return await AsyncTaskRepository(session=session).get_by_id(task_id)
```

FastAPI では `Depends(get_async_db_session)` または
`Depends(get_async_db_transaction)` を使用します。詳細は
[AsyncBaseRepository ガイド](docs/guides/repository/async_repository_guide.md)を
参照してください。

### 論理削除

```python
from repom import BaseModelAuto, BaseRepository, SoftDeletableMixin


class Article(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = "articles"


repo = BaseRepository(Article)
repo.soft_delete(1)
repo.restore(1)
repo.permanent_delete(1)
```

通常の `find()`、`get_by()`、`get_by_id()` は削除済み行を除外します。
詳細は [Soft Delete ガイド](docs/guides/model/soft_delete_guide.md)を参照してください。

## 設定

`RepomConfig` 単体の既定 DB は SQLite です。リポジトリ同梱の
`.env.example` は、repom 自身の開発用に
`CONFIG_HOOK=repom.config_hook:hook_config` を有効にしており、`dev` / `prod`
では PostgreSQL、`test` ではインメモリ SQLite を選びます。利用側プロジェクトは
自身の `CONFIG_HOOK` でこの方針を上書きできます。

```bash
cp .env.example .env
uv run repom_info
```

代表的な環境変数:

| 変数 | 用途 |
| --- | --- |
| `EXEC_ENV` | `dev` / `test` / `prod`。既定は `dev` |
| `CONFIG_HOOK` | `module:callable` 形式の設定フック |
| `DB_TYPE` | `sqlite` または `postgres` |
| `REPOM_DATABASE_URL` | DB URL の最優先 override |
| `REPOM_POSTGRES_DB` | PostgreSQL DB 名の固定 |
| `POSTGRES_*` | PostgreSQL 接続・ホストポート設定 |
| `PGADMIN_*` | pgAdmin 設定 |
| `REDIS_*` | Redis 接続・ホストポート設定 |
| `SQLITE_DB_PATH` / `SQLITE_DB_FILE` | SQLite ファイルの配置 |
| `SQLITE_USE_IN_MEMORY_FOR_TESTS` | test 環境でのインメモリ利用 |
| `SQLALCHEMY_*` | echo と接続プール設定 |

SQLite の自動ファイル名は `db_name` と `EXEC_ENV` から生成されます。既定の
`db_name=repom` では `repom_dev.sqlite3`、`repom_test.sqlite3`、
`repom.sqlite3` です。実際の有効値は `uv run repom_info` で確認してください。

設定フックでは、プロジェクト既定値を設定した後に必要な環境変数 helper を
適用します。

```python
from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides
from repom.config_hooks.sqlite import apply_sqlite_env_overrides


def hook_config(config):
    config.db_name = "myapp"
    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_sqlite_env_overrides(config)
    return config
```

詳細は [CONFIG_HOOK ガイド](docs/guides/features/config_hook_guide.md)と
[runtime override 一覧](docs/guides/postgresql/runtime_env_overrides.md)を
参照してください。

## コマンド

コマンドは `pyproject.toml` の `[project.scripts]` が正本です。

| 分類 | コマンド |
| --- | --- |
| DB | `db_create`, `db_delete` (`db_remove`), `db_backup`, `db_restore`, `db_sync_master` |
| 診断 | `repom_info`, `list_models` |
| Alembic | `alembic_init`, `alembic_reset`, `alembic` |
| PostgreSQL | `postgres_generate`, `postgres_start`, `postgres_stop`, `postgres_remove`, `postgres_rotate_credentials`, `pgadmin_rotate_password` |
| Redis | `redis_generate`, `redis_start`, `redis_stop`, `redis_remove`, `redis_rotate_password` |

すべて `uv run <command>` として実行します。

## テスト

```bash
uv run pytest
uv run pytest tests/unit_tests
uv run pytest tests/behavior_tests
uv run pytest -vv -s
```

外部プロジェクトでも同じ transaction rollback fixture を利用できます。

```python
# tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

非同期版は `create_async_test_fixtures()` です。詳しくは
[Testing Guide](docs/guides/testing/testing_guide.md)を参照してください。

## Alembic

revision の作成先と実行元は、どちらも `alembic.ini` の
`version_locations` で決まります。

```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic current
```

外部プロジェクトで repom の Alembic script を使う場合は、外部プロジェクト側の
`alembic.ini` に revision 保存先を指定してください。詳細は
[Alembic ガイド](docs/guides/features/alembic_migration_guide.md)を参照してください。

## ドキュメントと作業管理

- [ガイド一覧](docs/guides/README.md)
- [技術資料一覧](docs/technical/README.md)
- [機能アイデア](docs/ideas/README.md)
- [プロジェクト規約](AGENTS.md)

Issue とクロスプロジェクト提案はローカル Markdown ではなく issuekit API で
管理します。手順の正本は `issuekit protocol --role <role>` です。外部プロジェクト
への変更提案は `issuekit propose --to <project>` を使用します。
