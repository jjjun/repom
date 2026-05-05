# Issue #037: Config Display Command (repom_info)

**ステータス**: ✅ 完了

**作成日**: 2026-02-05

**完了日**: 2026-02-23

**優先度**: 中

**複雑度**: 低

## 問題の説明

repom の現在の設定状態（データベース接続、パス設定、モデル読み込み状況など）を確認する手段がない。デバッグや設定確認時に、現在の設定を一覧表示できるコマンドが必要。

## 期待される動作

`poetry run repom_info` コマンドで、現在の repom 設定を表示する。

### 表示項目

#### 1. 基本パス設定
- `config.root_path` - プロジェクトルート
- `config.backup_path` - バックアップディレクトリ
- `config.master_data_path` - マスターデータディレクトリ

#### 2. データベース設定
- `config.db_type` - データベースタイプ (sqlite / postgresql)
- `config.db_url` - 接続URL

#### 3. データベース固有設定

**SQLite の場合**:
- `db_file_path` - データベースファイルパス
- `db_file_exists` - ファイル存在確認
- `db_file_size` - ファイルサイズ（MB）

**PostgreSQL の場合**:
- `host` - ホスト名
- `port` - ポート番号
- `database` - データベース名
- `user` - ユーザー名

#### 4. PostgreSQL 接続テスト

**PostgreSQL の場合のみ表示**:
- `connection_status` - 接続テスト結果（成功/失敗）

#### 5. モデル読み込み設定
- `model_locations` - モデル検索パス
- `allowed_package_prefixes` - 許可パッケージプレフィックス
- `model_excluded_dirs` - 除外ディレクトリ
- `loaded_models` - 実際に読み込まれたモデル一覧
  - モデル名
  - テーブル名
  - パッケージパス

#### 6. 環境設定
- `EXEC_ENV` - 実行環境 (dev/test/prod)
- `CONFIG_HOOK` - カスタム設定フック（設定されている場合）

### 出力フォーマット

```
====================================
repom Configuration Information
====================================

[Basic Paths]
  Root Path         : /path/to/project
  Backup Path       : /path/to/project/data/repom/backups
  Master Data Path  : /path/to/project/data_master

[Database Configuration]
  Type              : sqlite
  URL               : sqlite:///data/repom/db.dev.sqlite3
  
  [SQLite Details]
    File Path       : /path/to/project/data/repom/db.dev.sqlite3
    File Exists     : Yes
    File Size       : 2.5 MB

[PostgreSQL Connection Test]
  (Not applicable for SQLite)

[Model Loading Configuration]
  Model Locations   : ['repom.examples.models']
  Allowed Prefixes  : {'repom.', 'mine_py.'}
  Excluded Dirs     : {'base', 'mixin', '__pycache__'}
  
  [Loaded Models] (3 models found)
    1. User
       - Table      : users
       - Package    : repom.examples.models.user
    2. Post
       - Table      : posts
       - Package    : repom.examples.models.post
    3. Comment
       - Table      : comments
       - Package    : repom.examples.models.comment

[Environment]
  EXEC_ENV          : dev
  CONFIG_HOOK       : Not set

====================================
```

### オプション（将来的な拡張案）

- `--json` - JSON 形式で出力
- `--verbose` - より詳細な情報（各モデルのカラム情報など）
- `--check-db` - データベース接続テストを実施

## 実装計画

### 1. スクリプト作成

**ファイル**: `repom/scripts/repom_info.py`

**実装内容**:
```python
from repom.config import config
from repom._.discovery import auto_import_models_from_list
from repom.database import Base
import os
from pathlib import Path

def format_size(size_bytes):
    """ファイルサイズを MB 単位でフォーマット"""
    return f"{size_bytes / (1024 * 1024):.2f} MB"

def get_db_file_info():
    """SQLite ファイル情報を取得"""
    # db_url から file path を抽出
    # 存在確認とサイズ取得

def test_postgres_connection():
    """PostgreSQL 接続テスト"""
    # db_engine を使って接続テスト
    
def get_loaded_models():
    """読み込まれたモデル一覧を取得"""
    # Base.metadata.tables から取得
    
def display_config():
    """設定情報を整形して表示"""
    # セクションごとに表示
```

### 2. Poetry Scripts 登録

**ファイル**: `pyproject.toml`

```toml
[tool.poetry.scripts]
repom_info = "repom.scripts.repom_info:main"
```

### 3. 実装の詳細

#### 3.1 基本パス表示
- `config.root_path` を Path オブジェクトとして表示
- 相対パスは絶対パスに変換

#### 3.2 SQLite 情報
- `db_url` から `sqlite:///` を除去してファイルパスを抽出
- `os.path.exists()` で存在確認
- `os.path.getsize()` でサイズ取得

#### 3.3 PostgreSQL 情報
- `db_url` を parse して host, port, database, user を抽出
- `db_engine.connect()` で接続テスト
- 成功/失敗を表示

#### 3.4 モデル情報
- `auto_import_models_from_list(config.model_locations)` でモデル読み込み
- `Base.metadata.tables` から全テーブル取得
- 各テーブルの `__tablename__`, `__module__`, `__name__` を表示

#### 3.5 環境変数
- `os.getenv('EXEC_ENV')` を取得
- `os.getenv('CONFIG_HOOK')` を取得

### 4. エラーハンドリング

- データベース接続失敗時: エラーメッセージを表示（スクリプトは続行）
- モデル読み込み失敗時: エラーメッセージを表示
- ファイルが存在しない場合: "File not found" と表示

## テスト計画

### 単体テスト

**ファイル**: `tests/unit_tests/test_repom_info.py`

#### テストケース

1. **test_format_size()**
   - バイト数を MB に変換する関数をテスト

2. **test_get_db_file_info_exists()**
   - SQLite ファイルが存在する場合の情報取得

3. **test_get_db_file_info_not_exists()**
   - SQLite ファイルが存在しない場合

4. **test_get_loaded_models()**
   - モデル一覧取得をテスト
   - User, Post などのテストモデルで検証

5. **test_display_config_sqlite()**
   - SQLite 設定での出力をテスト
   - 出力内容を文字列として検証

6. **test_display_config_postgresql()**
   - PostgreSQL 設定での出力をテスト
   - Mock を使用して接続テストをシミュレート

7. **test_command_execution()**
   - `poetry run repom_info` コマンドの実行テスト
   - subprocess で実行して exit code を確認

### 実行テスト

```bash
# SQLite 環境で実行
$env:EXEC_ENV='dev'
poetry run repom_info

# PostgreSQL 環境で実行（Docker 起動後）
$env:EXEC_ENV='dev'
$env:CONFIG_HOOK='tests.fixtures.config:get_postgres_config'
poetry run repom_info
```

### テスト観点

- ✅ 基本パスが正しく表示される
- ✅ SQLite ファイル情報が正しく表示される
- ✅ PostgreSQL 接続情報が正しく表示される
- ✅ モデル一覧が正しく表示される
- ✅ 環境変数が正しく表示される
- ✅ データベース接続失敗時でもスクリプトがクラッシュしない
- ✅ モデルが1つもない場合でもエラーにならない

## 完了基準

- ✅ `poetry run repom_info` コマンドが動作する
- ✅ SQLite 環境で全情報が正しく表示される
- ✅ PostgreSQL 環境で全情報が正しく表示される
- ✅ 単体テストが全てパスする（最低 7 テスト）
- ✅ README.md の "Available Commands" セクションに追加

## 影響範囲

### 新規作成ファイル
- `repom/scripts/repom_info.py`
- `tests/unit_tests/test_repom_info.py`

### 変更ファイル
- `pyproject.toml` - Poetry scripts 追加
- `README.md` - コマンドドキュメント追加

## 実装の注意点

### 1. データベース接続テスト

PostgreSQL の接続テストは **軽量** にする:
```python
def test_postgres_connection():
    try:
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "✓ Connected"
    except Exception as e:
        return f"✗ Failed: {str(e)}"
```

### 2. モデル読み込みのタイミング

- `auto_import_models_from_list()` は **初回のみ** 実行
- すでに読み込まれている場合はスキップ
- `Base.metadata.tables` から取得するだけ

### 3. セキュリティ

- **パスワードは表示しない**
- `db_url` にパスワードが含まれる場合は `***` でマスク

### 4. エラーハンドリング

- データベース接続失敗でもスクリプトは続行
- エラーメッセージは簡潔に

### 5. パフォーマンス

- ファイルサイズ取得は高速
- 接続テストは1回のみ
- 全体の実行時間は 1 秒以内を目標

## 将来的な拡張案

### Phase 2（今回は実装しない）

1. **JSON 出力オプション**
   ```bash
   poetry run repom_info --json
   ```

2. **詳細モード**
   ```bash
   poetry run repom_info --verbose
   # 各モデルのカラム情報も表示
   ```

3. **ヘルスチェックモード**
   ```bash
   poetry run repom_info --check
   # データベース接続、モデル読み込み、マイグレーション状態を確認
   # exit code で成功/失敗を返す
   ```

4. **設定ファイル出力**
   ```bash
   poetry run repom_info --export config.json
   # JSON 形式で設定をファイル出力
   ```

## 関連ドキュメント

- **README.md**: コマンドリファレンス
- **AGENTS.md**: プロジェクト構造
- **.github/copilot-instructions.md**: 開発ガイドライン

## 参考実装

類似機能を持つコマンド:
- `poetry run list_models` - モデル一覧表示
- `poetry run db_backup` - データベース操作

## 質問・検討事項

### 1. スクリプト名
- ❓ `repom_info` vs `repom_show_config` vs `repom_status`
- 推奨: `repom_info` (簡潔で覚えやすい)

### 2. 出力フォーマット
- ❓ テーブル形式 vs 階層形式 vs JSON
- 推奨: 階層形式（読みやすい）、将来的に `--json` オプション

### 3. モデル表示の詳細度
- ❓ モデル名のみ vs テーブル名付き vs カラム情報も
- 推奨: モデル名 + テーブル名 + パッケージパス

### 4. PostgreSQL 接続テスト
- ❓ 毎回実施 vs オプション指定時のみ
- 推奨: 毎回実施（軽量なので問題なし）

---

## ユーザーフィードバック（2026-02-05）

### 決定事項

1. **スクリプト名**: `repom_info` ✅
2. **出力フォーマット**: 階層形式 ✅
3. **モデル表示**: モデル名 + テーブル名 + パッケージパス ✅
4. **PostgreSQL接続テスト**: 独立した項目として表示 ✅
5. **PostgreSQL設定**: SQLite時は表示しない ✅
6. **VS Codeタスク**: 追加しない ✅
7. **Poetry scripts**: 追加する ✅

---

**次のステップ**: 実装 → テスト → ドキュメント更新

## テスト結果

- Unit tests: passed
