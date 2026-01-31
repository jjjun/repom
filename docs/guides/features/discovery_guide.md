# Generic Package Discovery Infrastructure Guide

**repom._.discovery** は、フレームワーク非依存の汎用的なパッケージディスカバリー・インポートシステムです。

## 📋 目次

- [概要](#概要)
- [基本機能](#基本機能)
- [主要な関数](#主要な関数)
- [使用例](#使用例)
- [ユースケース](#ユースケース)
- [エラーハンドリング](#エラーハンドリング)
- [セキュリティ](#セキュリティ)
- [ベストプラクティス](#ベストプラクティス)

---

## 概要

### 特徴

- **フレームワーク非依存**: SQLAlchemy に限定されず、あらゆる Python パッケージで使用可能
- **構造化されたエラーハンドリング**: 失敗情報を `DiscoveryFailure` として返却
- **セキュリティ検証**: ホワイトリスト方式でインポート対象を制限
- **柔軟なフック機構**: インポート完了後に任意の処理を実行可能

### ユースケース

- **SQLAlchemy モデル**: repom.models 自動インポート
- **FastAPI ルーター**: app/routes ディレクトリから自動登録
- **Celery タスク**: tasks ディレクトリから自動検出
- **プラグイン システム**: plugins ディレクトリから動的ロード

---

## 基本機能

### 1. パス正規化

文字列、リスト、カンマ区切り文字列を統一的に扱います。

```python
from repom._.discovery import normalize_paths

# カンマ区切り文字列
paths = normalize_paths("app.routes,app.api,app.tasks")
# ['app.routes', 'app.api', 'app.tasks']

# リスト
paths = normalize_paths(["app.routes", "app.api"])
# ['app.routes', 'app.api']

# None（空リスト）
paths = normalize_paths(None)
# []
```

### 2. 構造化エラー

失敗情報を `DiscoveryFailure` として返却します。

```python
from repom._.discovery import DiscoveryFailure

failure = DiscoveryFailure(
    target="myapp.nonexistent",
    target_type="package",
    exception_type="ModuleNotFoundError",
    message="No module named 'myapp.nonexistent'"
)

# 辞書形式で取得
print(failure.to_dict())
# {
#     'target': 'myapp.nonexistent',
#     'target_type': 'package',
#     'exception_type': 'ModuleNotFoundError',
#     'message': "No module named 'myapp.nonexistent'"
# }
```

### 3. セキュリティ検証

ホワイトリスト方式で信頼できるパッケージのみをインポート。

```python
from repom._.discovery import validate_package_security

# 許可されたプレフィックス
allowed = {'myapp.', 'shared.', 'repom.'}

# OK
validate_package_security('myapp.routes', allowed)

# NG: ValueError が発生
validate_package_security('untrusted.package', allowed)
```

---

## 主要な関数

### import_packages()

**用途**: 複数のパッケージを一括インポート（浅いインポート）

```python
from repom._.discovery import import_packages

# 基本的な使い方
failures = import_packages(['myapp.routes', 'myapp.tasks'])
if failures:
    for f in failures:
        print(f"Failed: {f.target} - {f.message}")

# セキュリティ検証付き
failures = import_packages(
    'myapp.routes,myapp.tasks',
    allowed_prefixes={'myapp.', 'shared.'}
)

# エラー時に例外を発生
from repom._.discovery import DiscoveryError

try:
    import_packages(['nonexistent.package'], fail_on_error=True)
except DiscoveryError as e:
    print(f"Failed: {len(e.failures)} packages")
```

**特徴**:
- パッケージのトップレベルのみをインポート
- サブモジュールは自動的にインポートされない
- 軽量で高速

---

### import_from_directory()

**用途**: ディレクトリ内の Python ファイルを再帰的にインポート

```python
from pathlib import Path
from repom._.discovery import import_from_directory

# 基本的な使い方
failures = import_from_directory(
    directory=Path("src/myapp/routes"),
    base_package="myapp.routes"
)

# 除外ディレクトリを指定
failures = import_from_directory(
    directory="src/myapp/models",
    base_package="myapp.models",
    excluded_dirs={'base', 'utils', 'helpers', '__pycache__'}
)

# エラー時に例外を発生
failures = import_from_directory(
    directory="src/myapp/tasks",
    base_package="myapp.tasks",
    fail_on_error=True
)
```

**特徴**:
- ディレクトリを再帰的に走査
- `.py` ファイルを自動検出してインポート
- `__init__.py` や `_private.py` はスキップ
- アルファベット順に確実にインポート
- 除外ディレクトリを指定可能（デフォルト: `{'__pycache__'}`）

**インポート順序**:
```
myapp/routes/
├── __init__.py          # スキップ
├── _internal.py         # スキップ（_で始まる）
├── admin.py             # 1. インポート
├── api.py               # 2. インポート
└── users/
    ├── __init__.py      # スキップ
    ├── auth.py          # 3. インポート (myapp.routes.users.auth)
    └── profile.py       # 4. インポート (myapp.routes.users.profile)
```

---

### import_package_directory()

**用途**: パッケージ名を指定してディレクトリを自動検出し、再帰的にインポート

```python
from repom._.discovery import import_package_directory

# 基本的な使い方
failures = import_package_directory('myapp.models')

# セキュリティ検証付き
failures = import_package_directory(
    'myapp.routes',
    allowed_prefixes={'myapp.', 'shared.', 'repom.'}
)

# 除外ディレクトリを指定
failures = import_package_directory(
    'myapp.models',
    excluded_dirs={'base', 'mixin', 'tests'}
)
```

**特徴**:
- パッケージ名からディレクトリを自動取得
- `import_from_directory()` を内部で使用
- パッケージが存在しない場合は `DiscoveryFailure` を返却

---

### import_from_packages()

**用途**: 複数のパッケージを一括インポート + インポート完了後のフック実行

```python
from repom._.discovery import import_from_packages
from sqlalchemy.orm import configure_mappers

# 基本的な使い方
failures = import_from_packages([
    'myapp.routes',
    'myapp.tasks'
])

# フック付き（SQLAlchemy モデル用）
failures = import_from_packages(
    package_names=['myapp.models', 'shared.models'],
    post_import_hook=configure_mappers  # すべてのインポート完了後に実行
)

# カンマ区切り文字列でも可
failures = import_from_packages(
    'myapp.routes,myapp.api,myapp.tasks',
    allowed_prefixes={'myapp.'},
    fail_on_error=False
)
```

**特徴**:
- 複数パッケージを一括処理
- `post_import_hook` でインポート完了後の処理を実行
- SQLAlchemy の `configure_mappers()` との相性が良い
- 循環参照問題の解決に有効

---

## 使用例

### 例1: FastAPI ルーター自動登録

```python
# app/main.py
from fastapi import FastAPI
from repom._.discovery import import_from_directory
from pathlib import Path

app = FastAPI()

# ルーターを自動インポート
failures = import_from_directory(
    directory=Path(__file__).parent / "routes",
    base_package="app.routes",
    excluded_dirs={'__pycache__', 'tests'}
)

if failures:
    for f in failures:
        print(f"Warning: Failed to import {f.target}: {f.message}")
```

```python
# app/routes/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users():
    return {"users": []}
```

### 例2: Celery タスク自動登録

```python
# celery_app.py
from celery import Celery
from repom._.discovery import import_from_directory
from pathlib import Path

app = Celery('myapp')

# タスクを自動インポート
failures = import_from_directory(
    directory=Path(__file__).parent / "tasks",
    base_package="myapp.tasks"
)

if failures:
    print(f"Failed to import {len(failures)} tasks")
```

```python
# tasks/email.py
from celery_app import app

@app.task
def send_email(to: str, subject: str):
    print(f"Sending email to {to}")
```

### 例3: SQLAlchemy モデル一括インポート（循環参照対応）

```python
# models/__init__.py
from repom._.discovery import import_from_packages
from sqlalchemy.orm import configure_mappers

def load_all_models():
    """すべてのモデルをインポート後、マッパーを初期化"""
    failures = import_from_packages(
        package_names=['myapp.models', 'shared.models'],
        excluded_dirs={'base', 'mixin'},
        allowed_prefixes={'myapp.', 'shared.'},
        post_import_hook=configure_mappers  # 循環参照を解決
    )
    
    if failures:
        for f in failures:
            print(f"Warning: {f.target} - {f.message}")
    
    return failures
```

### 例4: プラグインシステム

```python
# plugins/loader.py
from repom._.discovery import import_from_directory
from pathlib import Path

class PluginManager:
    def __init__(self):
        self.plugins = []
    
    def load_plugins(self, plugin_dir: Path):
        """プラグインを動的にロード"""
        failures = import_from_directory(
            directory=plugin_dir,
            base_package="plugins",
            fail_on_error=False
        )
        
        if failures:
            for f in failures:
                print(f"Plugin load failed: {f.target}")
        
        # ロードされたプラグインを収集
        import sys
        for name, module in sys.modules.items():
            if name.startswith('plugins.') and hasattr(module, 'Plugin'):
                self.plugins.append(module.Plugin())
        
        return len(self.plugins)

# 使用例
manager = PluginManager()
count = manager.load_plugins(Path("plugins"))
print(f"Loaded {count} plugins")
```

---

## エラーハンドリング

### fail_on_error=False（デフォルト）

失敗情報を `DiscoveryFailure` のリストとして返却します。

```python
failures = import_from_packages(['myapp.routes', 'nonexistent.package'])

# 失敗した対象を確認
for failure in failures:
    print(f"Target: {failure.target}")
    print(f"Type: {failure.target_type}")
    print(f"Error: {failure.exception_type} - {failure.message}")
```

### fail_on_error=True

最初の失敗で `DiscoveryError` を発生させます。

```python
from repom._.discovery import DiscoveryError

try:
    import_from_packages(
        ['myapp.routes', 'nonexistent.package'],
        fail_on_error=True
    )
except DiscoveryError as e:
    print(f"Discovery failed with {len(e.failures)} error(s)")
    for failure in e.failures:
        print(f"  - {failure.target}: {failure.message}")
```

### ログ出力

```python
import logging
from repom._.discovery import import_from_packages

logging.basicConfig(level=logging.INFO)

failures = import_from_packages(['myapp.routes'])

if failures:
    logger = logging.getLogger(__name__)
    for f in failures:
        logger.error(
            "Import failed",
            extra=f.to_dict()  # 構造化ログ
        )
```

---

## セキュリティ

### ホワイトリスト方式

信頼できるパッケージプレフィックスのみを許可します。

```python
from repom._.discovery import import_from_packages

# 許可されたプレフィックス
ALLOWED_PREFIXES = {
    'myapp.',      # 自社アプリケーション
    'shared.',     # 共有ライブラリ
    'plugins.',    # 公式プラグイン
    'repom.'       # repom 自体
}

# セキュリティ検証付きインポート
failures = import_from_packages(
    ['myapp.routes', 'shared.utils'],
    allowed_prefixes=ALLOWED_PREFIXES
)

# untrusted.package はインポート時に ValueError が発生
try:
    import_from_packages(
        ['untrusted.package'],
        allowed_prefixes=ALLOWED_PREFIXES
    )
except ValueError as e:
    print(f"Security violation: {e}")
```

### 推奨事項

1. **常に allowed_prefixes を設定**: 動的インポートを使用する場合は必須
2. **最小権限の原則**: 必要最小限のプレフィックスのみを許可
3. **環境別設定**: 開発環境と本番環境で異なる設定を使用

```python
# config.py
import os

def get_allowed_prefixes():
    if os.getenv('ENV') == 'production':
        return {'myapp.', 'shared.'}
    else:
        return {'myapp.', 'shared.', 'test.', 'debug.'}
```

---

## ベストプラクティス

### 1. 除外ディレクトリを明示的に指定

```python
# Good: 明示的に指定
failures = import_from_directory(
    directory="src/myapp/models",
    base_package="myapp.models",
    excluded_dirs={'base', 'mixin', 'tests', 'migrations', '__pycache__'}
)

# Bad: デフォルトに頼る（__pycache__ のみ除外）
failures = import_from_directory(
    directory="src/myapp/models",
    base_package="myapp.models"
)
```

### 2. フックを活用して循環参照を解決

```python
from sqlalchemy.orm import configure_mappers

# Good: すべてインポート後にマッパー初期化
failures = import_from_packages(
    ['myapp.models.user', 'myapp.models.post'],
    post_import_hook=configure_mappers
)

# Bad: 個別にインポート + 個別に初期化（循環参照エラー）
import_package_directory('myapp.models.user')
configure_mappers()  # ← post がまだインポートされていない
import_package_directory('myapp.models.post')
```

### 3. エラーを適切にログ出力

```python
import logging

logger = logging.getLogger(__name__)

failures = import_from_packages(['myapp.routes'])

if failures:
    for f in failures:
        if f.exception_type == 'ModuleNotFoundError':
            logger.warning(f"Optional module not found: {f.target}")
        else:
            logger.error(f"Import failed: {f.target} - {f.message}")
```

### 4. テスト環境での注意点

```python
# テスト前にモジュールキャッシュをクリア
import sys

def clean_module_cache(prefix: str):
    """指定プレフィックスのモジュールをキャッシュから削除"""
    for key in list(sys.modules.keys()):
        if key.startswith(prefix):
            del sys.modules[key]

# テスト
def test_import():
    clean_module_cache('test_app.')
    
    failures = import_from_directory(
        directory="test_app",
        base_package="test_app"
    )
    
    assert len(failures) == 0
```

---

## 比較: 旧API vs 新API

| 旧API | 新API | 用途 |
|-------|-------|------|
| `auto_import_models()` | `import_from_directory()` | ディレクトリベース |
| `auto_import_models_by_package()` | `import_package_directory()` | パッケージベース |
| `auto_import_models_from_list()` | `import_from_packages()` | 一括インポート + フック |

### 移行例

**旧API**:
```python
from repom.utility import auto_import_models_from_list
from sqlalchemy.orm import configure_mappers

auto_import_models_from_list(
    package_names=['myapp.models'],
    excluded_dirs={'tests'},
    allowed_prefixes={'myapp.'},
    fail_on_error=False
)
configure_mappers()  # 別途呼び出し
```

**新API**:
```python
from repom._.discovery import import_from_packages
from sqlalchemy.orm import configure_mappers

import_from_packages(
    package_names=['myapp.models'],
    excluded_dirs={'tests'},
    allowed_prefixes={'myapp.'},
    fail_on_error=False,
    post_import_hook=configure_mappers  # フックで統合
)
```

---

## まとめ

repom の discovery インフラは以下の用途で使用できます：

- ✅ **SQLAlchemy モデル**: 循環参照対応の一括インポート
- ✅ **FastAPI ルーター**: 自動検出と登録
- ✅ **Celery タスク**: タスクの動的ロード
- ✅ **プラグインシステム**: 拡張機能の動的読み込み
- ✅ **その他**: あらゆる Python パッケージの自動インポート

**キーポイント**:
1. **構造化されたエラー**: `DiscoveryFailure` で失敗情報を管理
2. **セキュリティ**: ホワイトリスト方式で安全にインポート
3. **フック機構**: `post_import_hook` で柔軟な処理を実現
4. **フレームワーク非依存**: 汎用的な設計で再利用性が高い

詳細は [`repom/_.discovery.py`](../../../repom/_/discovery.py) のソースコードを参照してください。
