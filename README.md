# repom

`repom` は SQLAlchemy を用いた最小限の DB アクセスレイヤーを提供するモジュールです。<br>
アプリ固有のモデルやリポジトリは含めず、`BaseModel`・`BaseRepository`・共通ユーティリティのみを提供します。
各プロジェクトはこの土台を基に独自のドメインモデルを構築してください。

### すぐ使えるリポジトリの拡張ポイント

- **default_options / default_order_by**: クラス属性に設定するだけで、すべての取得系メソッドに既定の eager load とソートを適用できます。`options=[]` を渡すと eager load だけを無効化できます。
- **FilterParams + field_to_column**: フィールドとカラムのマッピングを置くだけで等価・部分一致・IN を自動生成。特殊な条件が必要なときだけ `_build_filters()` をオーバーライドしてください。

## 📚 詳細ガイド

このドキュメントは基本的な情報のみを記載しています。詳細な使用方法は以下のガイドを参照してください：

- **[BaseModelAuto & スキーマ自動生成ガイド](docs/guides/model/base_model_auto_guide.md)**
  - Pydantic スキーマ自動生成（`get_create_schema()`, `get_update_schema()`, `get_response_schema()`）
  - `@response_field` デコレータの使い方
  - FastAPI 統合の実装例
  - 前方参照の解決方法

- **[BaseRepository 基礎ガイド](docs/guides/repository/base_repository_guide.md)**
  - BaseRepository の基本的な使い方
  - CRUD 操作の実装パターン

- **[Repository 高度なガイド](docs/guides/repository/repository_advanced_guide.md)**
  - 検索・クエリ・ソート・ページネーション
  - **Eager loading サポート（joinedload, selectinload）- N+1 問題の解決** ⭐ NEW
  - `default_options` による自動 eager loading

- **[FilterParams ガイド](docs/guides/repository/repository_filter_params_guide.md)**
  - FastAPI クエリパラメータ統合
  - `as_query_depends()` メカニズム
  - 型安全な検索パラメータ

- **[AsyncBaseRepository ガイド](docs/guides/repository/async_repository_guide.md)** ⭐ NEW
  - 完全非同期版リポジトリ（FastAPI 向け）
  - AsyncSession による非同期データベース操作
  - **Eager loading サポート（N+1 問題の解決）**
  - `asyncio.gather` による並行処理パターン
  - 論理削除（SoftDelete）の非同期操作

- **[論理削除（Soft Delete）ガイド](docs/guides/model/soft_delete_guide.md)** ⭐ NEW
  - SoftDeletableMixin による論理削除機能
  - 削除済みレコードの自動フィルタリング
  - 復元・物理削除の管理
  - バッチ処理での活用

- **[セッション管理パターンガイド](docs/guides/repository/repository_session_patterns.md)**
  - トランザクション管理（`get_db_transaction()`, `transaction()`）
  - FastAPI Depends パターン
  - FastAPI Users 統合
  - セッションのライフサイクル管理
  - トラブルシューティング

- **[マスターデータ同期ガイド](docs/guides/features/master_data_sync_guide.md)**
  - `db_sync_master` コマンドの使い方
  - マスターデータファイルの作成方法
  - Upsert 操作とトランザクション管理
  - ベストプラクティスとトラブルシューティング

- **[ロギングガイド](docs/guides/features/logging_guide.md)**
  - repom のロギング機能（ハイブリッドアプローチ）
  - CLI ツール実行時の自動設定
  - アプリケーション使用時の制御方法
  - `config_hook` でのカスタマイズ
  - テスト時のログ制御

- **[Alembic マイグレーション管理ガイド](docs/guides/features/alembic_migration_guide.md)** ⭐ NEW
  - Alembic の基本的な使い方とコマンド
  - repom での設定と環境切り替え
  - 外部プロジェクトでの設定方法
  - 実践的な例（テーブル追加、カラム追加、データマイグレーション）
  - トラブルシューティングとベストプラクティス

## 目次

- [セットアップ](#セットアップ)
- [コマンドリファレンス](#コマンドリファレンス)
- [基本的な使い方](#基本的な使い方)
- [環境変数](#環境変数)
- [テスト実行](#テスト実行)
- [Alembic マイグレーション](#alembic-マイグレーション)
- [ドキュメント構造](#ドキュメント構造)
- [トラブルシューティング](#トラブルシューティング)

---

## セットアップ

### 必須環境

- **Python**: 3.12以上
- **Poetry**: 1.0以上（依存関係管理）

### インストール手順

```bash
# 1. リポジトリをクローン（または既存プロジェクトに配置）
cd /path/to/repom

# 2. 依存関係をインストール
poetry install

# 3. （オプション）PostgreSQL サポートを追加
poetry install --extras postgres

# 4. データベースを作成
poetry run db_create

# 5. マイグレーションを適用（必要な場合）
poetry run alembic upgrade head

# 6. テストを実行して動作確認
poetry run pytest tests/unit_tests
```

### Optional Dependencies

repom は以下のオプション機能を提供しています：

```bash
# PostgreSQL サポート (psycopg3)
poetry install --extras postgres

# 非同期 PostgreSQL サポート (asyncpg)
poetry install --extras postgres-async

# 非同期 SQLite サポート (aiosqlite)
poetry install --extras async

# 全ての非同期サポート
poetry install --extras async-all

# 複数のオプションを同時に有効化
poetry install --extras "postgres async"
```

### 環境変数の設定（オプション）

```bash
# .envファイルを作成（オプション）
# EXEC_ENV: 実行環境（dev/test/prod）デフォルトは'dev'
EXEC_ENV=dev

# CONFIG_HOOK: 親プロジェクトから設定を注入する場合
# CONFIG_HOOK=mine_py:hook_config
```

### 初回セットアップの確認

```bash
# Pythonから確認
poetry run python -c "from repom.config import config; print(config.db_url)"
# 出力例: sqlite:///C:/path/to/repom/data/repom/db.dev.sqlite3
```

---

## 基本的な使い方

### モデルの定義

```python
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from repom.models import BaseModelAuto

class Task(BaseModelAuto, use_id=True, use_created_at=True, use_updated_at=True):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(
      String(255),
      nullable=False,
      info={"description": "タスク名"}
    )
    description: Mapped[Optional[str]] = mapped_column(
      String,
      info={"description": "詳細"}
    )
    is_done: Mapped[bool] = mapped_column(
      Boolean,
      default=False,
      nullable=False,
      info={"description": "完了フラグ"}
    )
```

**モデル定義のポイント**:
- `BaseModelAuto` では `info` を付けるとスキーマ説明が自動生成されます
- `use_id` / `use_created_at` / `use_updated_at` は**クラス定義パラメータ**で指定
- 複合主キーの場合は `use_id=False` を指定
- テーブル名をファイル名に揃えたい場合は `get_plural_tablename()` の利用を検討

### リポジトリの実装

```python
from repom import BaseRepository
from your_project.models import Task

class TaskRepository(BaseRepository[Task]):
  pass

# 使用例
repo = TaskRepository(session=db_session)
task = repo.save(Task(title="新しいタスク"))
all_tasks = repo.find()
```

**Repository 定義のポイント**:
- `BaseRepository[Model]` の型引数からモデルが自動推論されます
- `__init__` は不要（必要な場合のみカスタムメソッドを追加）
- `default_options` を使うと eager loading の既定を設定できます
- クエリ条件が複雑なら FilterParams を利用してください

### エンティティの作成・更新

`save()` は**新規作成・更新の両方**に使えます。

```python
# 内部セッション: 自動 commit + refresh
repo = TaskRepository()
task = repo.save(Task(title="新しいタスク"))

# 外部セッション: flush のみ（commit は呼び出し側）
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = TaskRepository(session)
    task = repo.save(Task(title="トランザクション内"))
```

**詳細**: [セッション管理パターンガイド](docs/guides/repository/repository_session_patterns.md)

### FastAPI 統合

```python
from fastapi import APIRouter

# スキーマを生成
TaskResponse = Task.get_response_schema()

router = APIRouter()

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int):
    task = repo.get_by_id(task_id)
    return task.to_dict()
```

**詳細**: [BaseModelAuto & スキーマ自動生成ガイド](docs/guides/model/base_model_auto_guide.md)

### 論理削除（Soft Delete）

```python
from repom.models import BaseModelAuto, SoftDeletableMixin
from repom import BaseRepository

# モデルに Mixin を追加
class Article(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = "articles"
    title: Mapped[str] = mapped_column(String(200))

# Repository で論理削除
repo = BaseRepository(Article)
article = repo.soft_delete(article_id)  # 論理削除（deleted_at に日時を記録）
repo.restore(article_id)                 # 復元（deleted_at を NULL に戻す）
repo.permanent_delete(article_id)        # 物理削除（完全削除）

# 削除済みを除外して検索（デフォルト）
active_articles = repo.find()

# 削除済みも含めて検索
all_articles = repo.find(include_deleted=True)
```

**詳細**: [論理削除（Soft Delete）ガイド](docs/guides/model/soft_delete_guide.md)

---

## コマンドリファレンス

### 設定情報表示

```bash
# 現在の repom 設定を表示
poetry run repom_info
```

repom の現在の設定（データベース接続、パス設定、モデル読み込み状況など）を表示します。

**用途**:
- 現在読み込まれているモデル一覧の確認
- DB 種別/URL、パス設定、環境変数の確認
- 設定のトラブルシューティング

**表示内容**:
- 基本パス（root_path, backup_path, master_data_path）
- データベース設定（db_type, db_url）
- SQLite詳細情報（ファイルパス、存在確認、サイズ）
- PostgreSQL詳細情報（host, port, database, user）
- PostgreSQL接続テスト結果
- モデル読み込み設定（読み込まれたモデル一覧）
- 環境変数（EXEC_ENV, CONFIG_HOOK）

### データベース操作

```bash
# データベース作成
poetry run db_create

# バックアップ作成
poetry run db_backup

# データベース削除
poetry run db_delete

# マスターデータ同期（Upsert）
poetry run db_sync_master
```

**データベースファイルの場所:**
- 本番環境 (`EXEC_ENV=prod`): `data/repom/db.sqlite3`
- 開発環境 (`EXEC_ENV=dev`, デフォルト): `data/repom/db.dev.sqlite3`
- テスト環境 (`EXEC_ENV=test`): `data/repom/db.test.sqlite3`（テストフレームワークではインメモリDBを使用）

### マイグレーション操作

```bash
# マイグレーションファイル自動生成
poetry run alembic revision --autogenerate -m "description"

# マイグレーション適用（最新まで）
poetry run alembic upgrade head

# 現在のバージョン確認
poetry run alembic current

# マイグレーション履歴確認
poetry run alembic history
```

---

## 環境変数

### RepomConfig（概要）

RepomConfig は repom の設定オブジェクトです。`CONFIG_HOOK` で起動時に差し替えできます。
主なカテゴリ: DB / モデル自動インポート / ログ / パス / その他

```python
# myapp/config.py
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
  config.db_type = "postgres"
  config.postgres_db = "myapp"
  return config
```

```bash
CONFIG_HOOK=myapp.config:hook_config
```

### データベース接続設定

デフォルトで以下の接続プール設定が適用されます：

```python
# repom/config.py
@property
def engine_kwargs(self) -> dict:
    return {
        'pool_size': 10,           # 常時維持する接続数
        'max_overflow': 20,        # pool_sizeを超えて作成可能な追加接続数
        'pool_timeout': 30,        # 接続待ちタイムアウト（秒）
        'pool_recycle': 3600,      # 接続の再利用時間（秒）
        'pool_pre_ping': True,     # 使用前に接続をテスト
        'connect_args': {'check_same_thread': False}  # SQLite用
    }
```

**カスタマイズ方法:**

```python
# mine_py/config.py
from repom.config import RepomConfig  # Note: MineDbConfig is still available as an alias

class MinePyConfig(RepomConfig):
    @property
    def engine_kwargs(self) -> dict:
        base_kwargs = super().engine_kwargs
        # 大量の並列処理が必要な場合
        base_kwargs['pool_size'] = 20
        base_kwargs['max_overflow'] = 40
        return base_kwargs
```

### `EXEC_ENV`

実行環境を指定します。

- **値**: `dev` / `test` / `prod`
- **デフォルト**: `dev`

```powershell
# PowerShell
$env:EXEC_ENV='dev'

# Unix系
export EXEC_ENV=dev
```

**環境別データベース:**
- `prod`: `data/repom/db.sqlite3`
- `dev`: `data/repom/db.dev.sqlite3` (デフォルト)
- `test`: `data/repom/db.test.sqlite3`

**テスト実行時の注意:**

テストフレームワーク (`create_test_fixtures()`) を使う場合は自動的にインメモリDB (`sqlite:///:memory:`) を使用しますが、`EXEC_ENV=test` で直接実行する場合は `data/repom/db.test.sqlite3` が使用されます：

```python
from repom.config import config

# test 環境の場合（EXEC_ENV=test で直接実行）
config.exec_env = 'test'
print(config.db_url)
# 出力: sqlite:///C:/path/to/repom/data/repom/db.test.sqlite3

# テストフレームワーク使用時はインメモリDB
# create_test_fixtures() が自動的に sqlite:///:memory: を使用
```

**メリット:**
- ✅ **35倍高速**: ファイルI/Oなし、純粋なメモリ操作
- ✅ **ロック防止**: "database is locked" エラーが発生しない
- ✅ **自動クリーンアップ**: プロセス終了時に自動削除、手動削除不要

**外部プロジェクトでの設定:**

```python
# mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        # インメモリDBをオフにする場合（デフォルトはTrue）
        self.use_in_memory_db_for_tests = False
```

### `CONFIG_HOOK`

親プロジェクトから設定を注入します（オプション）。

```bash
# .env ファイル
CONFIG_HOOK=mine_py.config:get_repom_config
```

**用途例**:
- モデル自動インポート対象の追加
- 許可パッケージ prefix の制御
- テスト用 DB の切り替え

---

## テスト実行

**⚠️ 重要**: テスト作成時は必ず **[Testing Guide](docs/guides/testing/testing_guide.md)** を参照してください。

### 基本的なテスト実行

```bash
# すべてのテスト
poetry run pytest

# 詳細表示で実行
poetry run pytest -v

# ユニットテストのみ
poetry run pytest tests/unit_tests

# 特定のファイルのみ
poetry run pytest tests/unit_tests/test_config.py

# VS Code タスクから実行（推奨）
# - ⭐Pytest/unit_tests
# - 🧪Pytest/all
```

### テスト戦略（概要）

repom は **Transaction Rollback** 方式で高速かつ分離されたテストを提供します。
詳細・フィクスチャ例は [Testing Guide](docs/guides/testing/testing_guide.md) を参照してください。

**要点**:
- セッションスコープで DB を 1 回だけ作成
- 各テストはトランザクション内で実行し自動ロールバック
- `db_test`（function scope）を使うだけでクリーンな状態を維持

**最小フィクスチャ例**:
```python
# tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

---

## Alembic マイグレーション

主要コマンドのみを記載します。詳細は [Alembic マイグレーション管理ガイド](docs/guides/features/alembic_migration_guide.md) を参照してください。

**注意（PowerShell）**:
- `$env:EXEC_ENV` はセッション内に残るため、環境切替は明示的に行う
- 本番相当で実行する場合は `EXEC_ENV` をクリアしてから実行する

```powershell
# マイグレーションファイル自動生成
poetry run alembic revision --autogenerate -m "description"

# マイグレーション適用（最新まで）
poetry run alembic upgrade head

# 状態確認
poetry run alembic current
poetry run alembic history
```

---

## ドキュメント構造

このプロジェクトは体系的なドキュメント構造を採用しています。

### 📁 ディレクトリ構成

```
docs/
├── README.md           # ドキュメント構造
├── guides/             # 📖 使い方ガイド
├── ideas/              # 💡 機能提案
├── technical/          # 🔧 実装判断記録
└── issue/              # 📋 問題管理（active/completed）
  ├── README.md      # Issue インデックス
  ├── active/        # 作業中・未着手
  └── completed/     # 完了済み
```

### 🎯 主要ガイド

主要ガイドは [docs/guides/README.md](docs/guides/README.md) を参照してください。

### 🤖 AI エージェント協働

- **問題報告**: AI が Issue ファイルを作成し、解決をサポート
- **アイデア提案**: AI がテンプレートに沿ってドキュメント化
- **自動完了処理**: 完了時に自動的に `completed/` へ移動

詳細: `.github/copilot-instructions.md`

---

## トラブルシューティング

### テスト関連

```bash
# データベースをクリーンアップ
poetry run db_delete

# 依存関係を再インストール
poetry install --sync

# 再度テスト実行
poetry run pytest tests/unit_tests -v
```

### Alembic 関連

```powershell
# 現在の環境変数を確認
echo $env:EXEC_ENV

# 環境変数をクリア
Remove-Item Env:\EXEC_ENV

# 現在のバージョンを確認
poetry run alembic current
```

### 設定関連

```python
# データディレクトリの確認
poetry run python -c "from repom.config import config; print(config.data_path)"

# CONFIG_HOOK が正しく動作するか確認
poetry run python -c "from repom.config import config; print(config)"
```

---

## 関連ドキュメント

- **[AGENTS.md](AGENTS.md)**: AI アシスタント向けプロジェクト情報
- **[docs/guides/](docs/guides/)**: 全ガイド一覧（機能別に整理）
  - [model/](docs/guides/model/) - BaseModel、スキーマ生成、システムカラム、論理削除
  - [repository/](docs/guides/repository/) - リポジトリパターン、セッション管理、データベース接続
  - [features/](docs/guides/features/) - マスターデータ同期、ロギング、モデル自動インポート
  - [testing/](docs/guides/testing/) - テスト戦略とフィクスチャ
- **[docs/technical/](docs/technical/)**: 技術詳細と実装判断記録
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)**: GitHub Copilot 専用の指示

---
