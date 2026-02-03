# repom CONFIG_HOOK ガイド

## 概要

**CONFIG_HOOK** は repom の設定をカスタマイズするための仕組みです。環境変数で関数を指定するだけで、プログラムの起動時に repom の設定を柔軟に変更できます。

**主な用途**:
- 別プロジェクトから repom を使用する際の設定変更
- 環境ごとに異なるデータベース接続設定
- モデル自動インポートのディレクトリ指定
- ログファイルのパスやレベルの変更
- PostgreSQL 接続情報の設定

**動作タイミング**: repom のモジュール初期化時（`repom/config.py` 読み込み時）に自動実行されます。

---

## 目次

- [基本的な使い方](#基本的な使い方)
- [設定できる項目](#設定できる項目)
- [実践例](#実践例)
- [動作の仕組み](#動作の仕組み)
- [トラブルシューティング](#トラブルシューティング)
- [ベストプラクティス](#ベストプラクティス)

---

## 基本的な使い方

### 1. hook 関数を定義

プロジェクト内に設定変更用の関数を定義します：

```python
# mine_py/config.py
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    """repom の設定をカスタマイズ"""
    
    # データベース設定
    config.db_type = 'postgres'
    config.postgres_db = 'mine_py'
    
    # モデル自動インポート設定
    config.model_locations = ['mine_py.models']
    config.allowed_package_prefixes = {'mine_py.', 'repom.'}
    config.model_excluded_dirs = {'base', 'mixin', '__pycache__'}
    
    # ログ設定
    config.enable_sqlalchemy_echo = True
    config.sqlalchemy_echo_level = 'INFO'
    
    return config
```

### 2. 環境変数で指定

`.env` ファイルまたは環境変数で hook 関数を指定します：

```bash
# .env
CONFIG_HOOK=mine_py.config:hook_config
```

または PowerShell で直接設定：

```powershell
$env:CONFIG_HOOK='mine_py.config:hook_config'
```

### 3. 動作確認

repom をインポートすると自動的に適用されます：

```python
from repom.config import config

print(config.db_type)        # => 'postgres'
print(config.postgres_db)    # => 'mine_py_dev' (exec_env='dev' の場合)
print(config.model_locations) # => ['mine_py.models']
```

---

## 設定できる項目

CONFIG_HOOK で変更できる主な設定項目：

### データベース関連
- `db_type` - 'sqlite' または 'postgres'
- `db_url` - データベース接続 URL
- `db_path`, `db_file` - SQLite ファイルのパスと名前
- `postgres_host`, `postgres_port`, `postgres_user`, `postgres_password`, `postgres_db` - PostgreSQL 接続情報
- `use_in_memory_db_for_tests` - テスト時の in-memory DB 使用フラグ

### モデル自動インポート関連
- `model_locations` - インポート対象パッケージのリスト
- `allowed_package_prefixes` - 許可するパッケージプレフィックス（セキュリティ）
- `model_excluded_dirs` - 除外するディレクトリ名
- `model_import_strict` - Strict モード（許可リスト外でエラー）

**詳細**: [モデル自動インポートガイド](auto_import_models_guide.md)

### ログ関連
- `log_path`, `log_file` - ログファイルのパスと名前
- `enable_sqlalchemy_echo` - SQLAlchemy クエリログの有効化
- `sqlalchemy_echo_level` - ログレベル ('INFO' or 'DEBUG')

**詳細**: [ロギングガイド](logging_guide.md)

### パス関連
- `root_path` - プロジェクトルートパス
- `data_path` - データ保存先
- `master_data_path` - マスターデータパス
- `auto_create_dirs` - ディレクトリ自動作成フラグ

### その他
- `exec_env` - 実行環境 ('dev', 'test', 'prod')  
  **注意**: 通常は環境変数 `EXEC_ENV` で指定します

---

## 実践例

### 例1: mine-py プロジェクトでの使用

```python
# mine_py/config.py
from repom.config import RepomConfig
from pathlib import Path

def hook_config(config: RepomConfig) -> RepomConfig:
    """mine-py プロジェクト用の repom 設定"""
    
    # プロジェクトルートを設定
    config.root_path = str(Path(__file__).parent.parent)
    
    # PostgreSQL を使用
    config.db_type = 'postgres'
    config.postgres_db = 'mine_py'
    config.postgres_user = 'mine_user'
    config.postgres_password = 'mine_password'
    
    # モデル自動インポート
    config.model_locations = ['mine_py.models']
    config.allowed_package_prefixes = {'mine_py.', 'repom.'}
    
    # SQLAlchemy クエリログを有効化（開発環境のみ）
    if config.exec_env == 'dev':
        config.enable_sqlalchemy_echo = True
        config.sqlalchemy_echo_level = 'INFO'
    
    return config
```

```bash
# mine_py/.env
CONFIG_HOOK=mine_py.config:hook_config
EXEC_ENV=dev
```

### 例2: テスト専用設定

```python
# tests/config.py
from repom.config import RepomConfig

def hook_config_test(config: RepomConfig) -> RepomConfig:
    """テスト専用設定"""
    
    # in-memory SQLite を使用（高速化）
    config.use_in_memory_db_for_tests = True
    
    # クエリログを無効化（テスト出力をシンプルに）
    config.enable_sqlalchemy_echo = False
    
    # テスト用ログファイル
    config.log_file = 'test.log'
    
    return config
```

```bash
# テスト実行時
$env:CONFIG_HOOK='tests.config:hook_config_test'
poetry run pytest
```

### 例3: 環境別の複雑な設定

```python
# myapp/config.py
from repom.config import RepomConfig
from pathlib import Path
import os

def hook_config(config: RepomConfig) -> RepomConfig:
    """環境ごとに異なる設定を適用"""
    
    env = config.exec_env
    
    # 共通設定
    config.model_locations = ['myapp.models']
    config.allowed_package_prefixes = {'myapp.', 'repom.'}
    
    # 環境別設定
    if env == 'prod':
        # 本番環境: PostgreSQL
        config.db_type = 'postgres'
        config.postgres_host = os.getenv('DB_HOST', 'prod-db.example.com')
        config.postgres_db = 'myapp_prod'
        config.postgres_user = os.getenv('DB_USER', 'prod_user')
        config.postgres_password = os.getenv('DB_PASSWORD')
        
        # ログは詳細に
        config.enable_sqlalchemy_echo = False
        config.log_path = '/var/log/myapp'
        
    elif env == 'dev':
        # 開発環境: SQLite + クエリログ
        config.db_type = 'sqlite'
        config.enable_sqlalchemy_echo = True
        config.sqlalchemy_echo_level = 'INFO'
        
    elif env == 'test':
        # テスト環境: in-memory SQLite
        config.use_in_memory_db_for_tests = True
        config.enable_sqlalchemy_echo = False
    
    return config
```

---

## 動作の仕組み

### 初期化フロー

```
1. repom/config.py が読み込まれる
   ↓
2. RepomConfig クラスがインスタンス化される
   ↓
3. get_config_from_hook(config) が呼ばれる
   ↓
4. 環境変数 CONFIG_HOOK を読み取る
   ↓
5. 指定された関数を動的にインポート
   ↓
6. 関数を実行して config を変更
   ↓
7. 変更後の config が返される
   ↓
8. config.init() で初期化完了
```

### 内部実装（参考）

```python
# repom/_/config_hook.py（簡略版）
import os
import importlib

def get_config_from_hook(config):
    """環境変数で指定されたフック関数から設定を取得"""
    
    # 環境変数を取得
    hook_path = os.getenv('CONFIG_HOOK')
    
    if not hook_path:
        return config  # フックが指定されていない場合はそのまま返す
    
    # "module.path:function_name" をパース
    module_path, function_name = hook_path.rsplit(':', 1)
    
    # モジュールをインポート
    module = importlib.import_module(module_path)
    
    # 関数を取得して実行
    hook_function = getattr(module, function_name)
    config = hook_function(config)
    
    return config
```

### 実行タイミング

CONFIG_HOOK は **repom のモジュール初期化時（一度だけ）** 実行されます：

```python
# repom/config.py の最後
config = RepomConfig()
config.root_path = str(Path(__file__).parent.parent)

# ここで CONFIG_HOOK が実行される
config = get_config_from_hook(config)

config.init()
```

### 設定の伝播

CONFIG_HOOK で変更した設定は、repom 全体に即座に反映されます：

```python
# mine_py/config.py で PostgreSQL を設定
def hook_config(config):
    config.db_type = 'postgres'
    return config

# どこからでも設定が参照できる
from repom.config import config
print(config.db_type)  # => 'postgres'

# DatabaseManager も自動的に PostgreSQL を使用
from repom.database import _db_manager
engine = _db_manager.get_sync_engine()  # PostgreSQL engine
```

---

## トラブルシューティング

### Q1: CONFIG_HOOK が適用されない

**症状**: 環境変数を設定したのに、設定が反映されない

**確認方法**:

```python
import os
from repom.config import config

print("CONFIG_HOOK:", os.getenv('CONFIG_HOOK'))
print("db_type:", config.db_type)
```

**原因と対処**:

1. **環境変数が設定されていない**
   ```powershell
   # 確認
   echo $env:CONFIG_HOOK
   
   # 設定
   $env:CONFIG_HOOK='mine_py.config:hook_config'
   ```

2. **.env ファイルが読み込まれていない**
   ```python
   # repom は自動的に .env を読むが、カレントディレクトリに配置する必要がある
   # または明示的に読み込む
   from dotenv import load_dotenv
   load_dotenv('/path/to/.env')
   ```

3. **関数のパスが間違っている**
   ```bash
   # 正しい: module.path:function_name
   CONFIG_HOOK=mine_py.config:hook_config
   
   # 間違い: ファイルパスやスラッシュ
   CONFIG_HOOK=mine_py/config.py:hook_config  # ❌
   ```

### Q2: ImportError が発生する

**症状**: `ModuleNotFoundError: No module named 'mine_py'`

**原因**: Python パスにモジュールが含まれていない

**対処**:

```python
# プロジェクトルートを PYTHONPATH に追加
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

または `pyproject.toml` で設定：

```toml
[tool.poetry]
packages = [
    { include = "mine_py", from = "src" }
]
```

### Q3: 設定が部分的にしか反映されない

**症状**: 一部の設定だけが適用されている

**原因**: hook 関数で `return config` を忘れている

```python
# ❌ 間違い: return を忘れている
def hook_config(config):
    config.db_type = 'postgres'
    # return config  # これがないと変更が反映されない

# ✅ 正しい
def hook_config(config):
    config.db_type = 'postgres'
    return config
```

### Q4: 関数が見つからない

**症状**: `AttributeError: module 'mine_py.config' has no attribute 'hook_config'`

**原因**: 関数名のスペルミス

```bash
# 環境変数の関数名と実際の関数名を確認
CONFIG_HOOK=mine_py.config:hook_config

# Python ファイル内
def hook_config(config):  # ← 名前が一致しているか確認
    ...
```

### Q5: 循環インポートエラー

**症状**: `ImportError: cannot import name 'config' from partially initialized module`

**原因**: hook 関数内で repom のモジュールをインポートしようとしている

```python
# ❌ 間違い: 循環インポートを引き起こす
def hook_config(config):
    from repom.database import _db_manager  # これがエラーを起こす
    ...

# ✅ 正しい: config オブジェクトだけを操作
def hook_config(config):
    config.db_type = 'postgres'
    return config
```

---

## ベストプラクティス

### 1. hook 関数はシンプルに保つ

hook は初期化時に毎回実行されるため、重い処理（DB接続、ファイルスキャン、外部API呼び出し）は避けましょう。

```python
# ✅ Good
def hook_config(config: RepomConfig) -> RepomConfig:
    config.db_type = 'postgres'
    config.model_locations = ['mine_py.models']
    return config
```

### 2. 型ヒントを使う

型ヒントを使うことで、IDE の補完が効き、型エラーを事前に検出できます。

```python
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    ...
    return config
```

### 3. 機密情報は環境変数で管理

```python
import os

def hook_config(config: RepomConfig) -> RepomConfig:
    config.postgres_password = os.getenv('DB_PASSWORD')
    return config
```

### 4. 必要最小限の設定だけ変更

デフォルト値で十分な設定は変更せず、必要な項目だけ指定しましょう。

### 5. hook 関数の配置場所

プロジェクトルートの `config.py` に配置するのが推奨です。専用ファイルやネストしたディレクトリは避けましょう。

```
✅ mine_py/config.py
❌ mine_py/repom_hook.py
❌ mine_py/hooks/config.py
```

---

## まとめ

CONFIG_HOOK は repom の強力なカスタマイズ機構です：

✅ **メリット**:
- コードを変更せずに設定を変更できる
- 環境ごとに異なる設定を簡単に切り替え
- 複数プロジェクトで repom を共有しやすい
- 機密情報を環境変数で管理できる

⚠️ **注意点**:
- hook 関数はシンプルに保つ
- 重い処理は避ける
- 必ず `return config` を忘れない
- 循環インポートに注意

📚 **関連ドキュメント**:
- [モデル自動インポートガイド](auto_import_models_guide.md) - `model_locations` の詳細
- [ロギングガイド](logging_guide.md) - ログ設定のカスタマイズ
- [PostgreSQL ガイド](../postgresql/postgresql_setup_guide.md) - PostgreSQL 設定の詳細

---

**最終更新**: 2025-02-03  
**バージョン**: 1.0
