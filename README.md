# repom

`repom` は SQLAlchemy を用いた最小限の DB アクセスレイヤーを提供するモジュールです。<br>
アプリ固有のモデルやリポジトリは含めず、`BaseModel`・`BaseRepository`・共通ユーティリティのみを提供します。
各プロジェクトはこの土台を基に独自のドメインモデルを構築してください。

## 目次

- [セットアップ](#セットアップ)
- [使い方](#使い方)
- [ドキュメント](#ドキュメント)
- [カスタム型](#カスタム型repomcustom_types)

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

## 使い方

### 基本的なコマンド

```bash
# データベース操作
poetry run db_create        # データベース作成
poetry run db_backup        # バックアップ作成
poetry run db_delete        # データベース削除

# マイグレーション
poetry run alembic revision --autogenerate -m "description"  # マイグレーション生成
poetry run alembic upgrade head                              # マイグレーション適用

# テスト実行
poetry run pytest tests/unit_tests      # ユニットテスト
poetry run pytest tests/behavior_tests  # 振る舞いテスト
```

> ⚠️ **重要**: PowerShellで環境変数を扱う際の注意点については、[Alembicマイグレーション運用ガイド](docs/alembic-guide.md)を必ずお読みください。

## ドキュメント

### 運用ガイド
- **[Alembicマイグレーション運用ガイド](docs/alembic-guide.md)** - 環境変数の正しい扱い方とマイグレーションコマンド
- **[テストガイド](docs/tests.md)** - テストの実行方法と構成

### AI向けドキュメント
- [AGENTS.md](AGENTS.md) - AIアシスタント向けプロジェクト情報
- [GitHub Copilot Instructions](.github/copilot-instructions.md) - GitHub Copilot専用の指示

## カスタム型（`repom.custom_types`）

`repom` では SQLAlchemy の基本型を補完するために、いくつかの独自 TypeDecorator を提供しています。主な型と用途は次のとおりです。

- `CreatedAt` / `ISO8601DateTime` / `ISO8601DateTimeStr`：日時カラムを ISO8601 形式で扱うためのユーティリティ。
- `ListJSON`：Python のリストを JSON 文字列として安全に保存します。
- `StrEncodedArray`：CSV 形式で文字列を保存し、Python のリストへ変換します。
- `JSONEncoded`：テキストカラムに JSON を保存するための型。**非推奨**です。今後のモデルでは `sqlalchemy.JSON` を使用してください（既存コードの互換性のために残っています）。

これらの型を利用する場合は、SQLAlchemy 標準の型との互換性に注意しつつ、必要最小限の場面に限ってください。

### py-mine から利用する場合
- 実行環境は `.env` などで `EXEC_ENV` を設定することで切り替えます。`CONFIG_HOOK` 環境変数を使い、親プロジェクト(py-mine)はrepomの設定を読み書きできるようになっており、`.env` で `CONFIG_HOOK=mine_py:hook_config` を指定すると `src/mine_py/__init__.py` の `hook_config` から共通設定が適用されます(root_pathやdata_pathの設定がpy-mineに合わせたパスになる)。
- モデルの追加読み込みは `MineDbConfig.set_models_hook()` を設定します。`repom` 単体では `repom.config:load_models` を経由し、py-mine では `/src/mine_py/__init__.py` 内の `hook_config` で追加モデルのフックを登録しています。
- データ格納先は `CONFIG_HOOK` で指定したフック内から `data_path` を変更することで上書きできます。py-mine では `hook_config` 内で `data_path` を設定しています。
- Alembic のマイグレーション設定は `alembic.ini` に依存しています。マイグレーションファイルは `version_locations = %(here)s/alembic/versions` で指定されており、py-mine ルートで Alembic コマンドを実行すると py-mine ルートの `alembic.ini` が、`repom` 直下で実行すると `repom` 直下の `alembic.ini` が使われます。
- マイグレーションの実行例

  ```bash
  # データベースのマイグレーション (alembic_version テーブルが DB に追加されます)
  poetry run alembic upgrade head
  # マイグレーションファイルの作成
  poetry run alembic revision --autogenerate -m 'comment'
  ```

### 単体で利用する場合
- `repom` 直下に移動してから Poetry コマンドを実行してください。
- `.env` に記載している `CONFIG_HOOK=mine_py:hook_config` を削除、または空文字を入れると、`repom` が既定の `root_path` として扱われます。
- 外部から設定を注入する必要がある場合は、任意のフックを実装したうえで `CONFIG_HOOK` 環境変数に `パッケージ:関数` 形式で指定してください。

## 利用できる環境変数とデータディレクトリ

### `EXEC_ENV`

本番・開発・テスト環境を切り替える環境変数です。既定値は `dev` で、`repom.config_hook` の `Config` データクラス内でデフォルト値が `dev` として定義されています。

### データディレクトリが決まる順序

`.env` で `CONFIG_HOOK=mine_py:hook_config` を指定すると、フック側で `data_path` が設定されます。`CONFIG_HOOK` を指定しない場合は、既定値として `repom/data/repom` が利用されます。

### データディレクトリを変更する方法

- `.env` で `CONFIG_HOOK=mine_py:hook_config` を指定します。
- 用意したフックは `hook_config(config: dataclass)` の様に、設定値が `config` dataclass で渡されるので、`config.data_path = '絶対パス'` として設定

注意として、相対パスで指定をすると、py-mine の相対パス を期待するのですが、repom 内の相対パスになってしまうので、意図した挙動になりません。なので絶対パスで指定してください。


## Poetry スクリプトでの DB 操作

`repom` 単体での開発を行う場合は、パッケージ直下で次のコマンドを利用できます。
`CONFIG_HOOK=mine_py:hook_config` を指定していない場合、`poetry run` コマンドを実行すると自動的に `repom/data/repom` 以下に環境ごとの DB ファイルとバックアップ用ディレクトリが作成されます。

```bash
# repom ディレクトリで実行
poetry install

# データベースの作成 (EXEC_ENV=dev の場合は data/db.dev.sqlite3 が作成されます)
poetry run db_create

# バックアップ (data/backups/ にバックアップファイルが保存されます)
poetry run db_backup

# テーブルを全て削除 (バックアップ後に実行することを推奨)
poetry run db_remove
```

## マイグレーションの実行

alembicのマイグレーションを実行する際、データベースは `alembic.ini` で定義されています。
`.ini` ファイルでは動的に値を変更できないため、`alembic/env.py` ファイルで `config.set_main_option('sqlalchemy.url', DATABASE_URL)` を使用して環境に応じてDBを切り替えています。

開発環境と本番環境を指定してマイグレーションを実行するには、以下のように `EXEC_ENV` を設定して alembic コマンドを実行してください。

### Windows(cmd)

```
set EXEC_ENV=dev
alembic upgrade head
```

### Windows(ps)

```
$env:EXEC_ENV='dev'
alembic upgrade head
```

### Unix系OS(Linux, macOS)

```
export EXEC_ENV=dev
alembic upgrade head
```


## alembic の注意

- `alembic.ini` に日本語を含めると(コメント含め) `UnicodeDecodeError: 'cp932' codec can't decode byte 0x84` が発生します。

古いマイグレーションファイルを削除する際には、次の様に、DBに保存されているマイグレーション情報と共に削除する必要があります。

```
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


## モデル／リポジトリ実装サンプル

### アプリ固有モデルの例

```python
from sqlalchemy import Column, String

from repom.base_model import BaseModel


class Task(BaseModel):
    __tablename__ = "tasks"

    # ID はデフォルトで有効。作成日時が欲しい場合はフラグを立てる。
    use_created_at = True

    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
```

- `BaseModel` が `id` カラム (整数 / プライマリーキー) を自動付与します。
- `use_created_at = True` を設定すると `created_at` カラムが追加されます (型は `repom.custom_types.CreatedAt`)。
- `to_dict()` や `update_from_dict()` などのユーティリティをそのまま利用できます。

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


repo = TaskRepository(Task)
repo.save(Task(title="初回タスク"))
params = TaskFilterParams(keyword="初回")
tasks = repo.find(filters=repo._build_filters(params))
```

- `BaseRepository` は `get_by_id` / `find` / `save` / `remove` などの基本操作を提供します。
- `_build_filters` をオーバーライドして Pydantic ベースの検索パラメータを組み合わせることで、`find` や `count_by_params` から共通ロジックを利用できます。

### BaseRepository が提供する操作用ヘルパー

`repom/base_repository.py` には、リポジトリ実装で再利用できる CRUD ヘルパーがまとまっています。アプリ側で操作を行う際は、以下の関数を中心に活用してください。

- `save(instance) -> instance` / `remove(instance)` — 単一モデルの保存・削除をトランザクション付きで実行します。
- `dict_save(data) -> instance` / `dict_saves(data_list)` — dict からモデルを生成して保存します。
- `saves(instances)` — 複数インスタンスをまとめて保存します。
- `set_find_option(query, **kwargs)` — `offset`・`limit`・`order_by` を簡潔に適用します。

これらを利用することで、コミットやロールバック処理を各リポジトリで重複させることなく、`repom` 標準の動作に揃えられます。


