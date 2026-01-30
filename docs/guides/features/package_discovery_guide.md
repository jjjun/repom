# Generic Package Discovery Guide

## 概要

repom は汎用的なパッケージディスカバリーインフラを提供します。これにより、モデル、ルーター、タスクなど、あらゆる用途でパッケージを安全かつ簡単にインポートできます。

**モジュール**: `repom._.discovery`

## 基本機能

### 1. `import_packages()` - 汎用パッケージインポート

**最もシンプルな使い方:**

```python
from repom._.discovery import import_packages

# 単一パッケージ
failures = import_packages("myapp.routes")

# 複数パッケージ
failures = import_packages(["myapp.routes", "myapp.tasks", "myapp.api"])

# カンマ区切り文字列
failures = import_packages("myapp.routes,myapp.tasks,myapp.api")

# 失敗をチェック
if failures:
    for f in failures:
        print(f"{f.target} failed: {f.message}")
```

**セキュリティ検証付き:**

```python
# 許可されたプレフィックスのみインポート
failures = import_packages(
    ["myapp.routes", "shared.utils"],
    allowed_prefixes={'myapp.', 'shared.', 'repom.'}
)
```

**エラー時に例外を発生:**

```python
from repom._.discovery import DiscoveryError

try:
    import_packages(
        "myapp.routes,myapp.tasks",
        fail_on_error=True
    )
except DiscoveryError as e:
    print(f"Failed to import {len(e.failures)} packages")
    for failure in e.failures:
        print(f"  - {failure.target}: {failure.message}")
```

## 実用例

### 1. ルーターローダー（fast-domain）

```python
from repom._.discovery import import_packages, normalize_paths

class FastDomainConfig:
    router_paths: str = "myapp.routes,myapp.api"
    
    def load_routers(self):
        # パスを正規化してインポート
        failures = import_packages(
            self.router_paths,
            allowed_prefixes={'myapp.', 'shared.', 'fast_domain.'},
            fail_on_error=False  # 警告のみ
        )
        
        if failures:
            print(f"⚠️ {len(failures)} routers failed to load")
        
        # FastAPI にルーターを登録
        # ... ルーター登録処理 ...
```

### 2. タスクローダー

```python
from repom._.discovery import import_packages, DiscoveryFailure, DiscoveryError

def load_tasks(task_paths: str | list[str]) -> list[DiscoveryFailure]:
    """タスクパッケージをインポート"""
    
    failures = import_packages(
        task_paths,
        allowed_prefixes={'myapp.tasks.', 'shared.tasks.'},
        fail_on_error=False
    )
    
    if failures:
        print(f"❌ Failed to load {len(failures)} task packages:")
        for f in failures:
            print(f"  - {f.target}: {f.exception_type}: {f.message}")
    
    return failures

# 使用例
failures = load_tasks("myapp.tasks.daily,myapp.tasks.hourly")
```

### 3. プラグインローダー

```python
from repom._.discovery import import_packages, DiscoveryError

class PluginManager:
    def load_plugins(self, plugin_paths: list[str]):
        """プラグインを読み込む"""
        
        try:
            import_packages(
                plugin_paths,
                allowed_prefixes={'myapp.plugins.'},
                fail_on_error=True  # プラグイン読み込み失敗は致命的
            )
            print(f"✅ Loaded {len(plugin_paths)} plugins")
        except DiscoveryError as e:
            print(f"❌ Plugin loading failed:")
            for failure in e.failures:
                print(f"  - {failure.target}")
            raise

# 使用例
manager = PluginManager()
manager.load_plugins([
    'myapp.plugins.payment',
    'myapp.plugins.analytics',
    'myapp.plugins.notification'
])
```

## 設計思想

### シンプルさ重視

- **関数ベース**: 複雑なクラス階層なし
- **明確な責任**: パッケージをインポートするだけ
- **組み合わせ可能**: 他のヘルパー関数と連携

### 汎用性

- **用途非依存**: モデル、ルーター、タスク、プラグインなど何でも
- **フレームワーク非依存**: FastAPI、Flask、Django などどこでも使える
- **プロジェクト非依存**: repom 以外のプロジェクトでも使える

### 安全性

- **構造化エラー**: `DiscoveryFailure` で詳細な失敗情報
- **セキュリティ検証**: ホワイトリストベースの保護
- **柔軟なエラーハンドリング**: 警告モードと例外モードの切り替え

## 既存のモデルローダーとの違い

### `import_packages()` vs `auto_import_models_from_list()`

| 機能 | `import_packages()` | `auto_import_models_from_list()` |
|------|---------------------|----------------------------------|
| 用途 | 汎用（ルーター、タスクなど） | モデル専用 |
| インポート方法 | パッケージをそのまま | ディレクトリ走査 + 個別ファイル |
| `configure_mappers()` | なし | あり（SQLAlchemy 専用） |
| シンプルさ | ✅ 非常にシンプル | やや複雑 |

**使い分け:**

```python
# ルーター/タスク/プラグイン → import_packages()
import_packages("myapp.routes,myapp.tasks")

# モデル → auto_import_models_from_list()（従来通り）
auto_import_models_from_list(['myapp.models', 'shared.models'])
```

## ヘルパー関数の組み合わせ

repom の汎用ヘルパーは組み合わせて使えます：

```python
from repom._.discovery import (
    normalize_paths,
    validate_package_security,
    import_packages,
    DiscoveryFailure,
    DiscoveryError
)

def load_custom_packages(paths: str | list[str], allowed: set[str]) -> None:
    """カスタムローダーの例"""
    
    # 1. パスを正規化
    packages = normalize_paths(paths)
    
    # 2. セキュリティ検証
    for pkg in packages:
        validate_package_security(pkg, allowed, strict=False)
    
    # 3. インポート
    failures = import_packages(packages, fail_on_error=False)
    
    # 4. エラーハンドリング
    if failures:
        for f in failures:
            print(f"⚠️ {f.target}: {f.message}")
```

## トラブルシューティング

### Q: `import_packages()` でモデルが読み込めない

**A**: モデルには `auto_import_models_from_list()` を使ってください。`import_packages()` はパッケージをそのままインポートするだけで、ディレクトリ走査はしません。

### Q: セキュリティ検証で ValueError が発生する

**A**: `allowed_prefixes` に適切なプレフィックスを追加してください：

```python
import_packages(
    "myapp.routes",
    allowed_prefixes={'myapp.', 'shared.'}  # 'myapp.' を追加
)
```

### Q: 失敗したパッケージだけ特定したい

**A**: 返される `failures` リストをチェックしてください：

```python
failures = import_packages(["pkg1", "pkg2", "pkg3"])
failed_names = [f.target for f in failures]
print(f"Failed: {failed_names}")
```

## 関連ドキュメント

- [auto_import_models_guide.md](auto_import_models_guide.md) - モデル自動インポート
- [testing_guide.md](testing_guide.md) - テスト戦略
- **Issue #024**: 汎用パッケージディスカバリーインフラの実装

---

**最終更新**: 2026-01-30  
**バージョン**: 1.0
