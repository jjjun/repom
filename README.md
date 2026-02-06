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
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from repom.models import BaseModel

class Task(BaseModel):
    __tablename__ = "tasks"

    # フラグでカラムを制御
    use_id = True
    use_created_at = True
    use_updated_at = True

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
```

### リポジトリの実装

```python
from repom import BaseRepository
from your_project.models import Task
from sqlalchemy.orm import Session

class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)

# 使用例
repo = TaskRepository(session=db_session)
task = repo.save(Task(title="新しいタスク"))
all_tasks = repo.find()
```

### エンティティの作成・更新

`save()` メソッドは**新規作成でも更新でも使えます**：

```python
# セッションなし（内部セッション）: 自動 commit
repo = TaskRepository()
task = Task(title="新しいタスク")
task = repo.save(task)
# → add() + commit() + refresh() を自動実行
# → created_at, updated_at が正しく設定される

# 外部セッション使用時: flush のみ、commit は呼び出し側
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = TaskRepository(session)
    task = Task(title="トランザクション内")
    task = repo.save(task)
    # → add() + flush() のみ実行
    # → commit は with ブロック終了時に自動実行

# 更新
task.title = "更新されたタスク"
task = repo.save(task)
# → 同じメソッドで更新も可能

# 非同期版
from repom import AsyncBaseRepository
async_repo = AsyncBaseRepository(Task, session=async_session)
task = await async_repo.save(task)
```

⚠️ **重要**: 直接 `session.add()` + `session.flush()` を使う場合は、必ず `session.refresh()` を呼んでください。
ただし、**通常は `save()` メソッドを使うことを強く推奨します**（refresh 忘れによるバグを防げます）。

**トランザクション管理**:

repom の Repository は**内部セッションと外部セッションを自動判定**します：

- **内部セッション**（`session=None`で初期化）: 
  * `save()` が自動的に `commit()` と `refresh()` を実行
  * `created_at` / `updated_at` などの DB 自動設定値が即座に取得可能

- **外部セッション**（明示的に渡す）: 
  * `save()` は `flush()` のみ実行、`commit()` は呼び出し側の責任
  * `refresh()` は実行されないため、DB 自動設定値の取得には明示的な `refresh()` が必要
  * トランザクション境界を呼び出し側で制御可能

```python
# 内部セッション: 自動 commit + refresh
repo = TaskRepository()
task = repo.save(Task(title="タスク"))
assert task.created_at is not None  # 自動的に設定される

# 外部セッション: flush のみ、refresh は手動
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = TaskRepository(session)
    task = repo.save(Task(title="タスク"))
    
    # created_at はまだ None（flush のみ実行）
    assert task.created_at is None
    
    # 明示的に refresh すれば取得可能
    session.refresh(task)
    assert task.created_at is not None
    
    # commit は with ブロック終了時に自動実行
```

```python
# ❌ 非推奨: 手動で flush() を使うパターン（refresh を忘れるとバグになる）
session.add(task)
await session.flush()
await session.refresh(task)  # これを忘れると created_at が None
await session.commit()

# ✅ 推奨: save() を使うパターン（シンプルで安全）
task = await repo.save(task)
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

### テスト戦略：Transaction Rollback パターン

repom は **Transaction Rollback** 方式を採用し、高速かつ分離されたテスト環境を提供します。

**特徴**:
- ✅ **高速**: DB作成は1回のみ（session scope）、各テストはロールバックのみ
- ✅ **分離**: 各テストは独立したトランザクション内で実行
- ✅ **クリーン**: 自動ロールバックで確実にリセット

**パフォーマンス**:
- 従来方式（DB再作成）: ~30秒
- Transaction Rollback: ~3秒
- **約9倍の高速化を実現**

### テストフィクスチャ

#### 同期テスト（標準）

```python
# tests/conftest.py
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()

# テストでの使用
def test_create_user(db_test):
    user = User(name="test")
    db_test.add(user)
    db_test.flush()
```

#### 非同期テスト（FastAPI Users など）

FastAPI Users のような async ライブラリのテストには `async_db_test` を使用：

```python
# tests/conftest.py
from repom.testing import create_async_test_fixtures

async_db_engine, async_db_test = create_async_test_fixtures()

# テストでの使用
@pytest.mark.asyncio
async def test_create_user_async(async_db_test):
    from sqlalchemy import select
    
    user = User(name="test")
    async_db_test.add(user)
    await async_db_test.flush()
    
    stmt = select(User).where(User.name == "test")
    result = await async_db_test.execute(stmt)
    found = result.scalar_one_or_none()
    
    assert found is not None
```

**async サポートの依存関係**:

```bash
# SQLite async サポート
poetry add repom[async]

# PostgreSQL async サポート
poetry add repom[postgres-async]

# 両方サポート
poetry add repom[async-all]

# pytest-asyncio も必要
poetry add --group dev pytest-asyncio
```

**注意事項**:
- async では lazy loading が使えません（eager loading を使用）
- Transaction Rollback パターンは async でも同様に動作します
- テストで `repom.session`, `repom.db` などをインポートする場合は、**インポート前に `os.environ['EXEC_ENV'] = 'test'` を設定**（詳細は [Testing Guide](docs/guides/testing/testing_guide.md#no-such-tableエラーrepomsession-や-repomdb-を使用する場合) 参照）

- **`db_engine`**: session スコープ（全テストで1回だけDB作成）
- **`db_test`**: function スコープ（各テストで独立したトランザクション）
- **`EXEC_ENV=test`**: 自動的に `data/repom/db.test.sqlite3` を使用

### 外部プロジェクトでの使用

mine-py などの外部プロジェクトでも同じヘルパーを使用できます：

```python
# external_project/tests/conftest.py
import pytest
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()

# カスタム設定も可能
db_engine, db_test = create_test_fixtures(
    db_url="sqlite:///:memory:",
    model_loader=my_custom_loader
)
```

詳細: `repom/testing.py`

---

## Alembic マイグレーション

### ⚠️ 重要：環境変数の扱い（PowerShell）

PowerShell では `$env:EXEC_ENV` を一度設定すると、**セッション内で保持され続けます**。

#### ✅ 正しい使い方

**本番環境（デフォルト）:**
```powershell
# 環境変数をクリア
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic upgrade head
```

**開発環境:**
```powershell
# 毎回明示的に指定
$env:EXEC_ENV='dev'; poetry run alembic upgrade head
```

### マイグレーションコマンド

#### ファイル作成

```powershell
# 自動生成（モデル変更を検出）
poetry run alembic revision --autogenerate -m "description"
```

#### 適用とダウングレード

```powershell
# 本番環境
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic upgrade head

# 開発環境
$env:EXEC_ENV='dev'; poetry run alembic upgrade head

# 1つ前のバージョンに戻す
poetry run alembic downgrade -1
```

#### 状態確認

```powershell
# 現在のバージョンを確認
poetry run alembic current

# マイグレーション履歴を確認
poetry run alembic history
```

### Alembic 設定のカスタマイズ

#### repom 単体で使用する場合

デフォルトでは `alembic/versions/` ディレクトリにマイグレーションファイルが保存されます。
設定は `alembic.ini` に記述されています。

```ini
# repom/alembic.ini
[alembic]
script_location = alembic
version_locations = alembic/versions
```

#### 外部プロジェクトで使用する場合

外部プロジェクト（例: `mine-py`）で repom を使用する場合、独自の `alembic.ini` を作成します。

**1. alembic.ini を作成:**

```ini
# mine-py/alembic.ini
[alembic]
# repom の env.py を使用
script_location = submod/repom/alembic

# マイグレーションファイルの保存場所と読み込み場所
# %(here)s は alembic.ini があるディレクトリを指します
# ファイル作成（alembic revision）と実行（alembic upgrade）の両方で使用されます
version_locations = %(here)s/alembic/versions
```

**2. 環境変数で CONFIG_HOOK を設定（オプション）:**

モデルの自動インポートなど、repom の他の機能を使う場合のみ必要です。

```powershell
# .env ファイル または環境変数
CONFIG_HOOK=mine_py.config:get_repom_config
```

```python
# mine-py/src/mine_py/config.py
from repom.config import RepomConfig  # Note: MineDbConfig is still available as an alias

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # モデル自動インポート設定
        self.model_locations = ['mine_py.models']
        self.allowed_package_prefixes = {'mine_py.', 'repom.'}
        self.model_excluded_dirs = {'base', 'mixin', '__pycache__'}

def get_repom_config():
    return MinePyConfig()
```

**動作の仕組み:**

1. `alembic revision -m "message"` を実行
   - `alembic.ini` の `version_locations` で**ファイル作成場所**を決定
   - `mine-py/alembic/versions/` にファイルが作成される

2. `alembic upgrade head` を実行
   - `alembic.ini` の `script_location` から `env.py` を読み込み
   - `alembic.ini` の `version_locations` で**マイグレーションファイルの読み込み場所**を決定
   - 指定されたディレクトリのマイグレーションを実行

**重要なポイント:**

- ✅ **`alembic.ini` の `version_locations` が唯一の設定源**
  - ファイル作成と実行の両方で同じ場所を使用
  - 設定が1箇所だけなので混乱がない

- ✅ **repom の `alembic/versions/` は空です**
  - repom はライブラリであり、独自のマイグレーションを持つべきではありません
  - マイグレーションファイルは消費アプリケーション側（mine-py など）で管理してください

### ベストプラクティス

1. **マイグレーション前に必ずバックアップ**
   ```powershell
   poetry run db_backup
   ```

2. **開発環境で先にテスト**
   ```powershell
   $env:EXEC_ENV='dev'; poetry run alembic upgrade head
   # 問題なければ本番環境へ
   Remove-Item Env:\EXEC_ENV
   poetry run alembic upgrade head
   ```

3. **コマンド実行前に環境変数を明示的に設定**
   - 本番環境: `Remove-Item Env:\EXEC_ENV`
   - 開発環境: `$env:EXEC_ENV='dev'`

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

**最終更新**: 2025-12-25  
**バージョン**: 簡略版 v2.1 (ガイド再構成版)
