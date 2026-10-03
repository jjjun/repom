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

repom 自体を開発する場合、`uv sync` は dev dependency group 経由で PostgreSQL
（同期・非同期）、Redis、`aiosqlite` を含む開発用依存関係をインストールします。

### 別のプロジェクトで使う

別プロジェクトには Git dependency として追加します。

```bash
uv add "repom @ git+https://github.com/jjjun/repom.git"
```

PostgreSQL や Redis の機能が必要な場合は、利用する extras を指定します。例えば:

```bash
uv add "repom[postgres,postgres-async,redis] @ git+https://github.com/jjjun/repom.git"
```

配布 wheel には `repom` パッケージのみが含まれ、リポジトリ直下の `alembic/`
（`env.py`、`script.py.mako`）はインストールされません。repom の Alembic 環境を
使う場合は、mine-py や fast-domain と同様に Git submodule などで repom の checkout
を用意し、`script_location` をその checkout 内の `alembic/` に設定してください。
詳細は [Alembic migration ガイド](docs/guides/features/alembic_migration_guide.md)を参照してください。

## 基本的な使い方

### モデル

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseModel


class Task(BaseModel, use_id=True, use_created_at=True, use_updated_at=True):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        info={"description": "Task title"},
    )
```

FastAPI 向けの Pydantic スキーマ自動生成（旧 `BaseModelAuto`）は利用側フレーム
ワーク（fast-domain）に移管されました。

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

FastAPI では、読み取りには `Depends(get_async_db_session)`、書き込みには
`Depends(get_async_db_transaction, scope="function")` を使用します。
`scope="function"` には FastAPI >= 0.121.0 が必要です。デフォルト scope との違いと
`StreamingResponse` の注意は
[セッション管理パターンガイド](docs/guides/repository/repository_session_patterns.md)を、
その他の async 利用方法は
[AsyncBaseRepository ガイド](docs/guides/repository/async_repository_guide.md)を参照してください。

### 論理削除

```python
from repom import BaseModel, BaseRepository, SoftDeletableMixin


class Article(BaseModel, SoftDeletableMixin):
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
| `EXEC_ENV` | `dev` / `test` / `prod` (`production` は `prod` の別名)。既定は `dev`。未知の値では警告を出し、DB 名と SQLite ファイル名に `dev` の既定値を使います |
| `CONFIG_HOOK` | `module:callable` 形式の設定フック |
| `DB_TYPE` | `sqlite` または `postgres`。DB URL が設定されている場合は URL の backend が優先され、異なる値なら警告します |
| `REPOM_DATABASE_URL` | 最優先の DB URL override。`DB_TYPE` より URL の backend が優先され、`db_*` CLI と PostgreSQL の prod TLS 検証にもこの URL が使われます |
| `DATABASE_URL` | `REPOM_DATABASE_URL` が空の場合に使う fallback DB URL |
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

`EXEC_ENV=production` は大文字小文字と前後の空白を無視して `prod` として扱われ、未知の値では警告を出して開発用の既定値を使います。DB URL が明示されているかは `config.db_url_overridden` で確認できます。詳しくは [CONFIG_HOOK ガイド](docs/guides/features/config_hook_guide.md)を参照してください。

設定フックでは、プロジェクト既定値を設定した後に必要な環境変数 helper を
適用します。

```python
from repom.config_hooks import apply_repom_env_overrides


def hook_config(config):
    config.db_name = "myapp"
    apply_repom_env_overrides(config)
    return config
```

設定フックの詳細は [CONFIG_HOOK ガイド](docs/guides/features/config_hook_guide.md)を参照してください。

## コマンド

コマンドは `pyproject.toml` の `[project.scripts]` が正本です。

| 分類 | コマンド |
| --- | --- |
| DB | `db_create`, `db_delete` (`db_remove`), `db_backup`, `db_restore`, `db_sync_master` |
| 診断 | `repom_info`, `list_models` |
| Alembic | `alembic_init`, `alembic_reset`, `alembic` |
| PostgreSQL | `postgres_generate`, `postgres_start`, `postgres_stop`, `postgres_remove`, `postgres_rotate_credentials`, `pgadmin_rotate_password` |
| Redis | `redis_generate`, `redis_start`, `redis_stop`, `redis_remove`, `redis_rotate_password` |

`alembic` コマンドは `[project.scripts]` に登録された repom の console script では
なく、Alembic dependency が提供する CLI です。

すべて `uv run <command>` として実行します。

## 公開 API

`BaseModel`、`BaseRepository`、`AsyncBaseRepository`、`SoftDeletableMixin` は上の「基本的な使い方」で説明しています。

| 分野 | 名前 | ガイド |
| --- | --- | --- |
| リポジトリ | `BaseRepository`, `AsyncBaseRepository` | 一括操作と `get_or_create()` は [BaseRepository ガイド](docs/guides/repository/base_repository_guide.md)を参照してください |
| 検索パラメータ | `FilterParams`, `MatchMode`, `MatchColumn`, `contains_column`, `prefix_column` | [検索パラメータガイド](docs/guides/repository/repository_filter_params_guide.md) |
| 範囲検索 | `gte_column`, `gt_column`, `lte_column`, `lt_column` | [検索パラメータガイド](docs/guides/repository/repository_filter_params_guide.md) |
| 並び順 | `get_order_by_columns`, `get_order_by_default_value`, `get_order_by_values`, `VirtualColumnError` | [並び順ガイド](docs/guides/repository/order_by_guide.md) |
| モデル | `ManyToManyMixin` | [多対多リレーションシップガイド](docs/guides/model/many_to_many_guide.md) |
| カスタム型 | `UTCDateTime` | [システムカラムとカスタム型ガイド](docs/guides/model/system_columns_and_custom_types.md) |
| 一意制約 | `repom.exceptions.is_unique_violation`, `unique_violation_constraint_name` | [システムカラムとカスタム型ガイド](docs/guides/model/system_columns_and_custom_types.md#一意制約違反の判定) |
| セッション | `get_db_session`, `get_db_transaction`, `get_reusable_sync_session`, `get_reusable_async_session`, `get_reusable_*_transaction`, `get_standalone_*_transaction`, `get_lifespan_manager`, `dispose_engines`, `safe_db_url` | [セッション管理ガイド](docs/guides/repository/repository_session_patterns.md) |
| 設定 hook | `repom.config_hooks.apply_repom_env_overrides`, `repom.config_hooks.parsing` | [CONFIG_HOOK ガイド](docs/guides/features/config_hook_guide.md)、[実行時環境変数ガイド](docs/guides/postgresql/runtime_env_overrides.md) |
| Redis 設定 | `RedisConfig.connection_kwargs()`, `url()`, `safe_url()` | [Redis 設定ガイド](docs/guides/redis/redis_manager_guide.md) |
| Alembic | `AlembicSetup`, `AlembicReset`, `AlembicTemplates` | [Alembic ガイド](docs/guides/features/alembic_migration_guide.md) |
| テスト | `create_test_fixtures`, `create_async_test_fixtures` (`bind_global_manager`) | [テストガイド](docs/guides/testing/testing_guide.md) |
| 宣言的基底クラス | `repom.database.Base` | [システムカラムとカスタム型ガイド](docs/guides/model/system_columns_and_custom_types.md) |
| Repository 拡張 | `QueryBuilderMixin`, `create_repository_instance`, `get_model_from_repository_class` | [検索とフィルタガイド](docs/guides/repository/repository_advanced_guide.md) |
| バリデーション | `NulByteError` | [NUL byte validation ガイド](docs/guides/features/nul_byte_validation.md) |
| 診断 | `QueryAnalyzer` | [QueryAnalyzer ガイド](docs/guides/features/query_analyzer_guide.md) |
| ロギング | `make_timed_rotating_handler`, `DateNamedDailyFileHandler` | [ロギングガイド](docs/guides/features/logging_guide.md) |

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
`alembic_init` は `alembic.ini` がない場合に `RepomConfig.alembic_*` の値を使って生成しますが、
実行時に読み込まれる設定は `alembic.ini` のみです。

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
- [Security Policy](SECURITY.md)

Issue とクロスプロジェクト提案はローカル Markdown ではなく issuekit API で
管理します。手順の正本は `issuekit protocol --role <role>` です。外部プロジェクト
への変更提案は `issuekit propose --to <project>` を使用します。
