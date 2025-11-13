# repom

`repom` は SQLAlchemy を用いた最小限の DB アクセスレイヤーを提供するモジュールです。<br>
アプリ固有のモデルやリポジトリは含めず、`BaseModel`・`BaseRepository`・共通ユーティリティのみを提供します。
各プロジェクトはこの土台を基に独自のドメインモデルを構築してください。

## 目次

- [セットアップ](#セットアップ)
- [コマンドリファレンス](#コマンドリファレンス)
- [テスト実行詳細](#テスト実行詳細)
- [Alembic マイグレーション詳細](#alembic-マイグレーション詳細)
- [環境変数とディレクトリ構成](#環境変数とディレクトリ構成)
- [設定とカスタマイズ](#設定とカスタマイズ)
- [カスタム型](#カスタム型repomcustom_types)
- [モデル／リポジトリ実装サンプル](#モデルリポジトリ実装サンプル)
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

# 3. データベースを作成
poetry run db_create

# 4. マイグレーションを適用（必要な場合）
poetry run alembic upgrade head

# 5. テストを実行して動作確認
poetry run pytest tests/unit_tests
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

## コマンドリファレンス

### データベース操作

```bash
# データベース作成
poetry run db_create

# マスターデータベース作成
poetry run db_create_master

# バックアップ作成
poetry run db_backup

# データベース削除
poetry run db_delete
```

**データベースファイルの場所:**
- 本番環境 (`EXEC_ENV=prod`): `data/repom/db.sqlite3`
- 開発環境 (`EXEC_ENV=dev`): `data/repom/db.dev.sqlite3`
- テスト環境 (`EXEC_ENV=test`): `data/repom/db.test.sqlite3`

### マイグレーション操作

```bash
# マイグレーションファイル自動生成
poetry run alembic revision --autogenerate -m "description"

# 空のマイグレーションファイル作成
poetry run alembic revision -m "description"

# マイグレーション適用（最新まで）
poetry run alembic upgrade head

# 1つ前のバージョンに戻す
poetry run alembic downgrade -1

# 特定のバージョンに戻す
poetry run alembic downgrade <revision_id>

# すべてのマイグレーションを取り消す
poetry run alembic downgrade base

# 現在のバージョン確認
poetry run alembic current

# マイグレーション履歴確認
poetry run alembic history

# 既存DBをマイグレーション管理下に置く
poetry run alembic stamp head
```

### テスト実行

```bash
# すべてのテスト
poetry run pytest

# 詳細表示で実行
poetry run pytest -v

# ユニットテストのみ
poetry run pytest tests/unit_tests

# 振る舞いテストのみ
poetry run pytest tests/behavior_tests

# 特定のファイルのみ
poetry run pytest tests/unit_tests/test_config.py

# VS Code タスクから実行（推奨）
# - ⭐Pytest/unit_tests
# - 🧪Pytest/all
```

---

## テスト実行詳細

### テスト構造

```
tests/
├── conftest.py          # 全テスト向けの環境変数設定
├── db_test_fixtures.py  # DB セッションフィクスチャ
├── unit_tests/          # 共有コンポーネントの単体テスト
├── behavior_tests/      # 共有機能の振る舞いテスト
└── utils.py             # テスト補助関数
```

### 主なフィクスチャ

#### `pytest_configure` (`tests/conftest.py`)
- `EXEC_ENV=test` を自動設定し、テスト用 SQLite データベース（`data/repom/db.test.sqlite3`）を利用
- `CONFIG_HOOK` を空文字列にし、親プロジェクト（py-mine）の設定フックを無効化
- repom を単体でテストできる環境を提供

#### `db_test` フィクスチャ (`tests/db_test_fixtures.py`)
- テストごとにクリーンなデータベース環境を提供
- 各テスト関数の実行前に `db_create()` でデータベースを作成
- テスト実行後に `db_delete()` でデータベースを削除
- SQLAlchemy の `db_session` を yield
- **スコープ**: `function`（デフォルト）- テスト間での状態の持ち越しがなく、独立性を保証

### テストが利用する環境変数

#### `EXEC_ENV`
- テスト専用のデータベース設定を選択するため `test` に固定
- `conftest.py` の `pytest_configure` で自動設定
- 結果: `data/repom/db.test.sqlite3` が使用される

#### `CONFIG_HOOK`
- 親プロジェクトの設定フックを制御
- テスト時は空文字列に設定され、repom 単体での動作を保証
- 通常の開発時は `.env` で `CONFIG_HOOK=mine_py:hook_config` のように設定可能

### テストカバレッジ

#### Unit Tests (`tests/unit_tests/`)
- **`test_config.py`**: 設定クラスの動作検証（12テスト）
- **`test_model.py`**: BaseModel の機能検証（5テスト）
- **`test_repository.py`**: BaseRepository の CRUD 操作検証（17テスト）
- **`custom_types/`**: カスタム型の動作検証
  - `test_createdat.py`: CreatedAt 型（2テスト）
  - `test_jsonencoded.py`: JSONEncoded 型（5テスト）
  - `test_listjson.py`: ListJSON 型（5テスト）

#### Behavior Tests (`tests/behavior_tests/`)
- **`test_unique_key_handling.py`**: ユニークキー制約の振る舞い
- **`test_date_type_comparison.py`**: 日付型の比較と SQLite 型の挙動

**合計**: 42テスト以上

### 実行時の注意事項

#### データベースの扱い
- **並列実行は非推奨**: データベースを操作するテストが多いため、複数プロセス並列（`-n` オプション）は推奨されません
- **データベースの場所**: テストデータベースは `data/repom/db.test.sqlite3` に作成されます
- **クリーンアップ**: `db_test` フィクスチャが自動的にデータベースを削除しますが、テスト失敗時に残る場合があります

```bash
# 手動でクリーンアップする場合
poetry run db_delete

# または直接削除
Remove-Item data/repom/db.test.sqlite3  # Windows PowerShell
rm data/repom/db.test.sqlite3            # Unix系
```

#### テストの独立性
- 各テスト関数は独立したデータベースで実行されます
- テスト間でデータが共有されることはありません
- テストの実行順序に依存しない設計になっています

### CI/CD 環境での実行

GitHub Actions、GitLab CI、その他の CI 環境でも同じコマンドが使用できます：

```yaml
# GitHub Actions の例
- name: Run tests
  run: |
    poetry install
    poetry run pytest tests/unit_tests -v
```

---

## Alembic マイグレーション詳細

### ⚠️ 重要：環境変数の扱い（PowerShell）

PowerShell では `$env:EXEC_ENV` を一度設定すると、**セッション内で保持され続けます**。これは危険な動作を引き起こす可能性があります。

#### ❌ 間違った使い方

```powershell
# 開発環境を設定
$env:EXEC_ENV='dev'; poetry run alembic upgrade head

# この後、本番環境のつもりで実行しても dev のまま！
poetry run alembic upgrade head  # ← 危険！まだ dev を参照
```

#### ✅ 正しい使い方

**本番環境（デフォルト）:**
```powershell
# 環境変数をクリア（本番環境）
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic upgrade head

# または明示的に prod を指定
$env:EXEC_ENV='prod'; poetry run alembic upgrade head
```

**開発環境:**
```powershell
# 毎回明示的に指定
$env:EXEC_ENV='dev'; poetry run alembic upgrade head
```

**Unix系OS (Linux, macOS):**
```bash
# 開発環境
export EXEC_ENV=dev
alembic upgrade head

# または1行で
EXEC_ENV=dev alembic upgrade head
```

### マイグレーションコマンド詳細

#### マイグレーションファイルの作成

```powershell
# 自動生成（モデル変更を検出）
poetry run alembic revision --autogenerate -m "description"

# 空のマイグレーション（手動編集用）
poetry run alembic revision -m "description"
```

#### マイグレーションの適用（アップグレード）

```powershell
# 本番環境
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic upgrade head

# 開発環境
$env:EXEC_ENV='dev'; poetry run alembic upgrade head

# テスト環境
$env:EXEC_ENV='test'; poetry run alembic upgrade head
```

#### マイグレーションの取り消し（ダウングレード）

```powershell
# 1つ前のバージョンに戻す
poetry run alembic downgrade -1

# 特定のバージョンに戻す
poetry run alembic downgrade <revision_id>

# すべてのマイグレーションを取り消す
poetry run alembic downgrade base
```

#### 状態確認

```powershell
# 現在のバージョンを確認
poetry run alembic current

# マイグレーション履歴を確認
poetry run alembic history

# 環境変数の確認
echo $env:EXEC_ENV
```

#### 既存DBをマイグレーション管理下に置く

```powershell
# 現在のDB構造を特定のバージョンとしてマーク
poetry run alembic stamp head
```

### 古いマイグレーションファイルの削除手順

古いマイグレーションファイルを削除する際には、DB に保存されているマイグレーション情報と共に削除する必要があります。

```powershell
# 1. 現在のDBをバックアップ
poetry run db_backup

# 2. alembic_version テーブルをクリア（全マイグレーション履歴を削除）
poetry run alembic stamp base

# 3. 古いマイグレーションファイルを削除
Remove-Item alembic\versions\*.py

# 4. 現在のモデル状態で新しい初期マイグレーションを作成
poetry run alembic revision --autogenerate -m "initial migration"

# 5. 新しいマイグレーションを適用
poetry run alembic upgrade head
```

### トラブルシューティング

#### 本番環境のつもりが開発環境を操作してしまった場合

```powershell
# 1. 環境変数を確認
echo $env:EXEC_ENV

# 2. 環境変数をクリア
Remove-Item Env:\EXEC_ENV

# 3. 再度正しい環境で実行
```

#### 両環境のバージョンを確認

```powershell
# 本番環境
Remove-Item Env:\EXEC_ENV -ErrorAction SilentlyContinue
poetry run alembic current

# 開発環境
$env:EXEC_ENV='dev'; poetry run alembic current
```

#### 直接DBのバージョンを確認

```powershell
# 本番環境
sqlite3 data\repom\db.sqlite3 "SELECT * FROM alembic_version;"

# 開発環境
sqlite3 data\repom\db.dev.sqlite3 "SELECT * FROM alembic_version;"
```

### ベストプラクティス

1. **マイグレーション前に必ずバックアップ**
   ```powershell
   poetry run db_backup
   # または手動コピー
   Copy-Item data\repom\db.sqlite3 data\repom\backups\db_$(Get-Date -Format 'yyyyMMdd_HHmmss').sqlite3
   ```

2. **開発環境で先にテスト**
   ```powershell
   $env:EXEC_ENV='dev'; poetry run alembic upgrade head
   # 問題なければ本番環境へ
   Remove-Item Env:\EXEC_ENV
   poetry run alembic upgrade head
   ```

3. **マイグレーション後は必ず確認**
   ```powershell
   poetry run alembic current
   ```

4. **コマンド実行前に環境変数を明示的に設定**
   - 本番環境: `Remove-Item Env:\EXEC_ENV` または `$env:EXEC_ENV='prod'`
   - 開発環境: `$env:EXEC_ENV='dev'`

### SQLite の制約

SQLite は `ALTER TABLE` に制限があるため、複雑な変更は `batch_alter_table` を使用するか、手動SQLで対応する必要があります。

### Alembic の注意事項

- `alembic.ini` に日本語を含めると（コメント含め）`UnicodeDecodeError: 'cp932' codec can't decode byte 0x84` が発生します
- マイグレーションファイルは `alembic/versions/` に保存されます
- `alembic.ini` の `version_locations = %(here)s/alembic/versions` で指定されています
- py-mine ルートで Alembic コマンドを実行すると py-mine ルートの `alembic.ini` が使われます
- repom 直下で実行すると repom 直下の `alembic.ini` が使われます

---

## 環境変数とディレクトリ構成

### 環境変数一覧

#### `EXEC_ENV` / `PYMINE__CORE__ENV`

実行環境を指定する環境変数です。

- **値**: `dev` / `test` / `prod`
- **デフォルト**: `dev`
- **定義場所**: `repom.config_hook` の `Config` データクラス

**設定方法:**

```powershell
# PowerShell
$env:EXEC_ENV='dev'
$env:PYMINE__CORE__ENV='dev'  # 新しい推奨形式

# Unix系
export EXEC_ENV=dev
export PYMINE__CORE__ENV=dev
```

**環境別のデータベースファイル:**
- `prod`: `data/repom/db.sqlite3`
- `dev`: `data/repom/db.dev.sqlite3`
- `test`: `data/repom/db.test.sqlite3`

#### `CONFIG_HOOK`

親プロジェクトから設定を注入するためのフック関数を指定します。

- **形式**: `パッケージ名:関数名`
- **例**: `mine_py:hook_config`
- **デフォルト**: なし（repom 単体動作）

**設定方法:**

```bash
# .env ファイル
CONFIG_HOOK=mine_py:hook_config
```

**フック関数の実装例:**

```python
# mine_py/__init__.py
from repom.config_hook import Config

def hook_config(config: Config):
    """repom の設定をカスタマイズ"""
    # データディレクトリを変更
    config.data_path = '/absolute/path/to/data'
    
    # 追加モデルを登録
    config.models_hook = 'mine_py.models:load_models'
```

### データディレクトリ構成

#### デフォルトのディレクトリ構造

```
repom/
└── data/
    └── repom/                    # デフォルトの data_path
        ├── db.sqlite3            # 本番環境
        ├── db.dev.sqlite3        # 開発環境
        ├── db.test.sqlite3       # テスト環境
        ├── backups/              # バックアップ保存先
        │   └── db_20251113_120000.sqlite3
        └── logs/                 # ログファイル（将来用）
```

#### データディレクトリの決定順序

1. **CONFIG_HOOK が設定されている場合**
   - フック関数内で `config.data_path` を設定
   - 絶対パスで指定することを推奨

2. **CONFIG_HOOK が未設定の場合**
   - デフォルト: `repom/data/repom`

#### データディレクトリの変更方法

**注意**: 相対パスで指定すると、repom 内の相対パスになってしまうため、意図した挙動になりません。必ず**絶対パス**で指定してください。

```python
# mine_py/__init__.py
from pathlib import Path
from repom.config_hook import Config

def hook_config(config: Config):
    # ❌ 相対パス（非推奨）
    # config.data_path = 'data/mine_py'  # repom からの相対パスになる
    
    # ✅ 絶対パス（推奨）
    project_root = Path(__file__).parent.parent
    config.data_path = str(project_root / 'data' / 'mine_py')
```

---

## 設定とカスタマイズ

### py-mine から利用する場合

repom を py-mine プロジェクトから利用する際の設定方法です。

#### 1. 環境変数の設定

```bash
# .env ファイル
EXEC_ENV=dev
CONFIG_HOOK=mine_py:hook_config
```

#### 2. フック関数の実装

```python
# src/mine_py/__init__.py
from pathlib import Path
from repom.config_hook import Config

def hook_config(config: Config):
    """repom の設定を py-mine 用にカスタマイズ"""
    # プロジェクトルートを取得
    project_root = Path(__file__).parent.parent.parent
    
    # データディレクトリを py-mine 用に変更
    config.data_path = str(project_root / 'data' / 'mine_py')
    
    # 追加モデルのロード関数を登録
    config.models_hook = 'mine_py.models:load_models'
```

#### 3. 追加モデルの登録

```python
# src/mine_py/models/__init__.py
def load_models():
    """py-mine 固有のモデルをインポート"""
    from .user import UserModel
    from .task import TaskModel
    # ... 他のモデル
```

#### 4. Alembic マイグレーション設定

- py-mine ルートで Alembic コマンドを実行すると、py-mine ルートの `alembic.ini` が使われます
- マイグレーションファイルは `alembic/versions/` に保存されます

```bash
# py-mine ルートで実行
cd /path/to/py-mine
poetry run alembic upgrade head
```

### repom 単体で利用する場合

repom を単独で開発・テストする場合の設定方法です。

#### 1. 環境変数の設定

```bash
# .env ファイル
EXEC_ENV=dev
# CONFIG_HOOK は設定しない（または空文字列）
CONFIG_HOOK=
```

#### 2. コマンド実行

```bash
# repom ディレクトリで実行
cd /path/to/repom
poetry install
poetry run db_create
poetry run alembic upgrade head
poetry run pytest tests/unit_tests
```

#### 3. データディレクトリ

- デフォルト: `repom/data/repom`
- `poetry run` コマンドを実行すると自動的に作成されます

### カスタムフックの実装

任意のプロジェクトから repom を利用する場合のフック実装例です。

```python
# your_project/__init__.py
from pathlib import Path
from repom.config_hook import Config

def custom_hook(config: Config):
    """カスタム設定フック"""
    # データディレクトリを変更
    config.data_path = '/custom/path/to/data'
    
    # DB URLを直接指定（高度な用途）
    # config.db_url = 'postgresql://user:pass@localhost/dbname'
    
    # バックアップディレクトリを変更
    # config.db_backup_path = '/custom/backup/path'
    
    # 追加モデルを登録
    config.models_hook = 'your_project.models:load_models'
```

```bash
# .env ファイル
CONFIG_HOOK=your_project:custom_hook
```

---

## カスタム型（`repom.custom_types`）

`repom` では SQLAlchemy の基本型を補完するために、いくつかの独自 TypeDecorator を提供しています。

### 提供している型

#### 日時関連

- **`CreatedAt`**: 作成日時を ISO8601 形式で扱う型
- **`ISO8601DateTime`**: 日時カラムを ISO8601 形式で扱う型
- **`ISO8601DateTimeStr`**: 日時を ISO8601 文字列として扱う型

#### データ構造関連

- **`ListJSON`**: Python のリストを JSON 文字列として安全に保存
- **`StrEncodedArray`**: CSV 形式で文字列を保存し、Python のリストへ変換

#### 非推奨の型

- **`JSONEncoded`**: テキストカラムに JSON を保存するための型
  - **非推奨**: 今後のモデルでは `sqlalchemy.JSON` を使用してください
  - 既存コードの互換性のために残っています

### 使用例

```python
from sqlalchemy import Column, String, Integer
from repom.base_model import BaseModel
from repom.custom_types import CreatedAt, ListJSON

class MyModel(BaseModel):
    __tablename__ = 'my_table'
    
    use_id = True
    use_created_at = True  # CreatedAt 型が自動で使われる
    
    name = Column(String(100), nullable=False)
    tags = Column(ListJSON, nullable=True)  # リストを JSON で保存
```

### 注意事項

- SQLAlchemy 標準の型との互換性に注意してください
- 必要最小限の場面に限って使用してください
- 新規開発では SQLAlchemy 2.0 の標準型（`JSON` など）を優先してください

---

## モデル／リポジトリ実装サンプル

### アプリ固有モデルの例

```python
from sqlalchemy import Column, String
from repom.base_model import BaseModel

class Task(BaseModel):
    __tablename__ = "tasks"

    # ID はデフォルトで有効。作成日時が欲しい場合はフラグを立てる。
    use_id = True
    use_created_at = True
    use_updated_at = True

    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
```

**BaseModel の主な機能:**
- `id` カラム（整数/プライマリーキー）を自動付与
- `use_created_at = True` で `created_at` カラムを追加（型: `repom.custom_types.CreatedAt`）
- `use_updated_at = True` で `updated_at` カラムを追加
- `to_dict()`: モデルを辞書に変換
- `update_from_dict()`: 辞書からモデルを更新

### リポジトリクラスの例

```python
from typing import Optional
from repom.base_repository import BaseRepository, FilterParams
from your_project.models import Task

class TaskFilterParams(FilterParams):
    keyword: Optional[str] = None

class TaskRepository(BaseRepository[Task]):
    def _build_filters(self, params: Optional[TaskFilterParams]):
        filters = []
        if params and params.keyword:
            filters.append(Task.title.ilike(f"%{params.keyword}%"))
        return filters

# 使用例
repo = TaskRepository(Task)
repo.save(Task(title="初回タスク"))
params = TaskFilterParams(keyword="初回")
tasks = repo.find(filters=repo._build_filters(params))
```

**BaseRepository の主な機能:**
- `get_by_id(id)`: ID でモデルを取得
- `find(filters)`: 条件に一致するモデルを検索
- `save(instance)`: モデルを保存
- `remove(instance)`: モデルを削除
- `_build_filters()`: Pydantic ベースの検索パラメータを組み立て

### BaseRepository が提供する操作用ヘルパー

`repom/base_repository.py` には、リポジトリ実装で再利用できる CRUD ヘルパーがまとまっています。

#### 基本操作

- **`save(instance) -> instance`**: 単一モデルの保存をトランザクション付きで実行
- **`remove(instance)`**: 単一モデルの削除をトランザクション付きで実行
- **`saves(instances)`**: 複数インスタンスをまとめて保存

#### 辞書からの操作

- **`dict_save(data) -> instance`**: dict からモデルを生成して保存
- **`dict_saves(data_list) -> list[instance]`**: 複数の dict からモデルを生成して保存

#### 検索オプション

- **`set_find_option(query, **kwargs)`**: `offset`・`limit`・`order_by` を簡潔に適用

```python
# 使用例
query = session.query(Task)
query = repo.set_find_option(query, offset=10, limit=20, order_by='created_at.desc')
```

これらを利用することで、コミットやロールバック処理を各リポジトリで重複させることなく、`repom` 標準の動作に揃えられます。

---

## トラブルシューティング

### テスト関連

#### テストが失敗する場合

```bash
# 1. 環境変数を確認
echo $env:EXEC_ENV  # PowerShell
echo $EXEC_ENV      # Unix系

# 2. データベースをクリーンアップ
poetry run db_delete

# 3. 依存関係を再インストール
poetry install --sync

# 4. 再度テスト実行
poetry run pytest tests/unit_tests -v
```

#### モジュールが見つからないエラー

```bash
# 依存関係をインストール
poetry install

# 仮想環境が有効になっているか確認
poetry env info
```

### Alembic 関連

#### 本番環境と開発環境を間違えた

```powershell
# 1. 現在の環境変数を確認
echo $env:EXEC_ENV

# 2. 環境変数をクリア
Remove-Item Env:\EXEC_ENV

# 3. 正しい環境で再実行
```

#### マイグレーションが適用されない

```powershell
# 1. 現在のバージョンを確認
poetry run alembic current

# 2. マイグレーション履歴を確認
poetry run alembic history

# 3. 手動でバージョンをマーク（初回のみ）
poetry run alembic stamp head
```

#### データベースファイルが見つからない

```powershell
# 1. データディレクトリを確認
poetry run python -c "from repom.config import config; print(config.db_file_path)"

# 2. データベースを作成
poetry run db_create
```

### 設定関連

#### CONFIG_HOOK が動作しない

```python
# 1. フック関数が正しく定義されているか確認
# mine_py/__init__.py
def hook_config(config):
    print(f"hook_config called: {config}")
    # ... 設定

# 2. 環境変数が正しく設定されているか確認
# .env
CONFIG_HOOK=mine_py:hook_config

# 3. Python から確認
poetry run python -c "from repom.config import config; print(config.data_path)"
```

#### データディレクトリが期待と違う

```python
# 絶対パスで指定されているか確認
def hook_config(config):
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    config.data_path = str(project_root / 'data')  # 絶対パス
```

### データベース関連

#### データベースがロックされている

```bash
# すべてのPythonプロセスを終了
# その後、再度実行
```

#### バックアップが見つからない

```bash
# バックアップディレクトリを確認
ls data/repom/backups/

# 手動でバックアップ作成
poetry run db_backup
```

---

## 付録

### プロジェクト構造

```
repom/
├── repom/                      # Main package
│   ├── custom_types/          # Reusable custom SQLAlchemy types
│   ├── scripts/               # CLI scripts (Poetry entry points)
│   ├── base_model.py          # Base SQLAlchemy model helpers
│   ├── base_repository.py     # Base repository abstraction
│   ├── base_static.py         # Base static model class
│   ├── config.py              # Environment-aware configuration
│   ├── config_hook.py         # Configuration hook system
│   ├── db.py                  # Database connection setup
│   └── utility.py             # Shared utility functions
├── tests/                     # Test suite
│   ├── unit_tests/           # Unit tests
│   ├── behavior_tests/       # Behavioral tests
│   ├── conftest.py           # Pytest configuration
│   └── db_test_fixtures.py   # Database fixtures
├── alembic/                  # Database migration files
├── data/                     # SQLite databases
├── docs/                     # Additional documentation
│   ├── base_model_auto_guide.md
│   └── issue/
├── pyproject.toml           # Poetry configuration
├── pytest.ini              # Pytest configuration
└── alembic.ini             # Alembic configuration
```

### 主な依存関係

- **sqlalchemy**: ORM and database toolkit (2.0+)
- **alembic**: Database migration management
- **pydantic**: Data validation and serialization
- **python-dotenv**: Environment variable management
- **inflect**: Pluralization utilities
- **pytest**: Testing framework with extensions
- **pytest-sqlalchemy**: SQLAlchemy testing utilities
- **pytest-benchmark**: Performance testing

### 開発ガイドライン

- shared logic を minimal に保つ（framework-agnostic）
- アプリ固有のモデル・リポジトリは consuming project で定義
- `BaseRepository` のメソッド（`get_by` など）を利用してモデル操作を統一
- `tests/db_test_fixtures.py` のフィクスチャを再利用
- 新しい shared utilities を追加する場合は `tests/unit_tests/` にテストを追加

### AI エージェント向け情報

- このドキュメントは AI エージェント（GitHub Copilot、Cursor など）向けに最適化されています
- すべての主要情報を README.md に集約しています
- `docs/` 配下のファイルは補足資料です（詳細な技術ドキュメント）
- プロジェクト構造、技術スタック、開発ガイドラインは [AGENTS.md](AGENTS.md) も参照
- GitHub Copilot 向けの追加指示は [.github/copilot-instructions.md](.github/copilot-instructions.md) を参照

### 関連ドキュメント

- **[AGENTS.md](AGENTS.md)**: AI アシスタント向けプロジェクト情報
- **[docs/base_model_auto_guide.md](docs/base_model_auto_guide.md)**: BaseModelAuto と response_field 機能ガイド
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)**: GitHub Copilot 専用の指示

---

**最終更新**: 2025-11-13  
**バージョン**: 統合版 v1.0
