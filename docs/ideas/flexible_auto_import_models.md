# 柔軟な auto_import_models 設定

## ステータス
- **段階**: アイディア
- **優先度**: 中
- **複雑度**: 低
- **作成日**: 2025-11-15
- **最終更新**: 2025-11-15

## 概要

`auto_import_models` を任意の場所に指定できるようにし、設定で指定した複数のディレクトリ配下のモデルを Alembic に自動認識させる機能を追加します。

## モチベーション

### 現在の問題

**現状の使い方**:
```python
# models/__init__.py で直接呼び出す
from pathlib import Path
from repom.utility import auto_import_models

auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='myapp.models'
)
```

**問題点**:
1. **手動呼び出しが必要**
   - 各プロジェクトで `models/__init__.py` に記述が必要
   - Alembic の `env.py` で明示的にインポートする必要がある

2. **単一ディレクトリのみサポート**
   - 複数の models ディレクトリがある場合、それぞれで呼び出しが必要
   - モノレポ構成で共有モデルと個別モデルを扱いにくい

3. **Alembic との統合が手動**
   - `env.py` でモデルをインポートし忘れる可能性
   - マイグレーションファイル生成時にモデルが認識されないことがある

4. **柔軟性の欠如**
   - 動的にモデルディレクトリを追加できない
   - 環境によってモデルのロード元を変更できない

### 理想の動作

**設定ベースの自動インポート**:
```python
# repom/config.py または alembic/env.py
from repom.config import CONFIG

CONFIG.MODEL_LOCATIONS = [
    'myapp.models',           # メインのモデル
    'myapp.admin.models',     # 管理画面用モデル
    'shared.models',          # 共有モデル
]

# Alembic が自動的にすべてのモデルを認識
poetry run alembic revision --autogenerate -m "add new models"
```

**環境変数での指定**:
```bash
# 開発環境では追加のモデルをロード
export MODEL_LOCATIONS="myapp.models,myapp.dev_models,shared.models"

# 本番環境では本番用モデルのみ
export MODEL_LOCATIONS="myapp.models,shared.models"
```

## ユースケース

### 1. モノレポ構成
```python
# プロジェクト構造
workspace/
├── shared/
│   └── models/
│       ├── user.py
│       └── session.py
├── api/
│   └── models/
│       ├── product.py
│       └── order.py
└── admin/
    └── models/
        └── audit_log.py

# 設定で一括指定
CONFIG.MODEL_LOCATIONS = [
    'shared.models',
    'api.models',
    'admin.models',
]

# すべてのモデルが自動的に Alembic に認識される
```

### 2. プラグイン/拡張モデル
```python
# メインアプリ + プラグインモデル
CONFIG.MODEL_LOCATIONS = [
    'myapp.models',           # コアモデル
    'plugins.payment.models', # 支払いプラグイン
    'plugins.analytics.models', # 分析プラグイン
]

# プラグインの有効/無効で動的にモデルを追加
if CONFIG.ENABLE_PAYMENT_PLUGIN:
    CONFIG.MODEL_LOCATIONS.append('plugins.payment.models')
```

### 3. テスト環境専用モデル
```python
# 本番環境
if CONFIG.EXEC_ENV == 'prod':
    CONFIG.MODEL_LOCATIONS = [
        'myapp.models',
    ]
# テスト環境
elif CONFIG.EXEC_ENV == 'test':
    CONFIG.MODEL_LOCATIONS = [
        'myapp.models',
        'tests.fixtures.models',  # テスト用モデル
    ]
```

### 4. 段階的なマイグレーション
```python
# レガシーモデルと新モデルを並行運用
CONFIG.MODEL_LOCATIONS = [
    'myapp.models.legacy',    # 旧モデル
    'myapp.models.v2',        # 新モデル
]

# 移行完了後は新モデルのみ
CONFIG.MODEL_LOCATIONS = [
    'myapp.models.v2',
]
```

## 検討可能なアプローチ

### アプローチ 1: 設定ファイルベース
**説明**: `MineDbConfig` に `MODEL_LOCATIONS` を追加し、Alembic の `env.py` で自動ロード

**長所**:
- 宣言的で分かりやすい
- 環境変数でオーバーライド可能
- 中央集約された設定

**短所**:
- 設定の変更が必要
- 既存の実装への影響

**実装**:
```python
# repom/config.py
class MineDbConfig:
    # 既存の設定...
    
    # モデルの自動インポート設定
    MODEL_LOCATIONS: List[str] = os.getenv(
        'MODEL_LOCATIONS',
        'myapp.models'  # デフォルト
    ).split(',')
    
    # 除外ディレクトリ
    MODEL_EXCLUDED_DIRS: Set[str] = {
        'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'
    }
    
    @classmethod
    def auto_import_all_models(cls):
        """設定されたすべてのモデルディレクトリからモデルをインポート"""
        from repom.utility import auto_import_models_by_package
        
        for package_name in cls.MODEL_LOCATIONS:
            try:
                auto_import_models_by_package(
                    package_name=package_name,
                    excluded_dirs=cls.MODEL_EXCLUDED_DIRS
                )
            except Exception as e:
                print(f"Warning: Failed to import models from {package_name}: {e}")

# alembic/env.py
from repom.config import CONFIG

def run_migrations_offline():
    # モデルを自動インポート
    CONFIG.auto_import_all_models()
    
    # 以降の処理...

def run_migrations_online():
    # モデルを自動インポート
    CONFIG.auto_import_all_models()
    
    # 以降の処理...
```

### アプローチ 2: パッケージ名ベースのユーティリティ
**説明**: `auto_import_models` を拡張し、パッケージ名から自動的にディレクトリを解決

**長所**:
- 既存の `auto_import_models` を拡張
- パッケージ名のみで指定可能（パス不要）
- より Pythonic

**短所**:
- パッケージの解決に失敗する可能性
- 実装がやや複雑

**実装**:
```python
# repom/utility.py

def auto_import_models_by_package(
    package_name: str,
    excluded_dirs: Optional[Set[str]] = None
) -> None:
    """
    Import all models from a package by package name.
    
    Args:
        package_name: Python package name (e.g., 'myapp.models')
        excluded_dirs: Set of directory names to exclude
    
    Example:
        auto_import_models_by_package('myapp.models')
        auto_import_models_by_package('shared.models')
    """
    try:
        # パッケージをインポートして __path__ を取得
        package = importlib.import_module(package_name)
        if not hasattr(package, '__path__'):
            raise ValueError(f"{package_name} is not a package")
        
        # パッケージのディレクトリを取得
        package_dir = Path(package.__path__[0])
        
        # 既存の auto_import_models を呼び出し
        auto_import_models(
            models_dir=package_dir,
            base_package=package_name,
            excluded_dirs=excluded_dirs
        )
    except ImportError as e:
        raise ImportError(f"Failed to import package {package_name}: {e}")


def auto_import_models_from_list(
    package_names: List[str],
    excluded_dirs: Optional[Set[str]] = None
) -> None:
    """
    Import models from multiple packages.
    
    Args:
        package_names: List of package names
        excluded_dirs: Set of directory names to exclude
    
    Example:
        auto_import_models_from_list([
            'myapp.models',
            'shared.models',
            'plugins.payment.models'
        ])
    """
    for package_name in package_names:
        try:
            auto_import_models_by_package(package_name, excluded_dirs)
        except Exception as e:
            print(f"Warning: Failed to import models from {package_name}: {e}")
```

### アプローチ 3: Alembic 拡張プラグイン
**説明**: Alembic のフック機構を使ってモデルを自動ロード

**長所**:
- Alembic の標準的な拡張方法
- `env.py` の変更を最小限に
- プラグインとして再利用可能

**短所**:
- Alembic の内部構造への理解が必要
- やや複雑

**実装**:
```python
# repom/alembic_plugin.py

class RepomAlembicPlugin:
    """Alembic plugin for auto-importing repom models"""
    
    def __init__(self, config):
        self.config = config
    
    def before_revision(self):
        """Called before generating a revision"""
        self._import_models()
    
    def before_upgrade(self):
        """Called before upgrading"""
        self._import_models()
    
    def _import_models(self):
        """Import all configured model packages"""
        from repom.config import CONFIG
        CONFIG.auto_import_all_models()

# alembic/env.py
from repom.alembic_plugin import RepomAlembicPlugin

plugin = RepomAlembicPlugin(config)
plugin.before_revision()  # マイグレーション生成前に実行
```

## 技術的考慮事項

### パッケージの解決
```python
# パッケージ名からディレクトリを自動解決
import importlib
import sys

def resolve_package_path(package_name: str) -> Path:
    """パッケージ名から実際のファイルシステムパスを取得"""
    try:
        module = importlib.import_module(package_name)
        if hasattr(module, '__path__'):
            return Path(module.__path__[0])
        else:
            # モジュールファイル自体のパス
            return Path(module.__file__).parent
    except ImportError:
        raise ValueError(f"Package {package_name} not found")
```

### 循環インポートの防止
```python
# インポート済みパッケージのキャッシュ
_imported_packages: Set[str] = set()

def auto_import_models_by_package(package_name: str, ...):
    # すでにインポート済みならスキップ
    if package_name in _imported_packages:
        return
    
    # インポート実行
    ...
    
    # キャッシュに追加
    _imported_packages.add(package_name)
```

### エラーハンドリング
```python
def auto_import_all_models_safe(
    package_names: List[str],
    fail_on_error: bool = False
) -> Dict[str, Optional[Exception]]:
    """
    すべてのパッケージからモデルをインポート（エラートラッキング付き）
    
    Returns:
        Dict[str, Optional[Exception]]: パッケージ名とエラーのマッピング
    """
    results = {}
    for package_name in package_names:
        try:
            auto_import_models_by_package(package_name)
            results[package_name] = None  # 成功
        except Exception as e:
            results[package_name] = e
            if fail_on_error:
                raise
            else:
                print(f"Warning: Failed to import {package_name}: {e}")
    return results
```

### パフォーマンス最適化
```python
# 遅延インポート: 必要になるまでインポートしない
class LazyModelImporter:
    def __init__(self, package_names: List[str]):
        self.package_names = package_names
        self._imported = False
    
    def ensure_imported(self):
        """必要になった時点でインポート"""
        if not self._imported:
            auto_import_models_from_list(self.package_names)
            self._imported = True

# Alembic env.py で使用
model_importer = LazyModelImporter(CONFIG.MODEL_LOCATIONS)
model_importer.ensure_imported()  # マイグレーション実行時のみ
```

## 統合ポイント

### 影響を受けるコンポーネント
- `repom/utility.py` - `auto_import_models_by_package` 関数の追加
- `repom/config.py` - `MODEL_LOCATIONS` 設定の追加
- `alembic/env.py` - 自動インポートの統合
- `README.md` - 新機能のドキュメント化
- `docs/guides/repository_and_utilities_guide.md` - 使用例の追加

### 既存機能との相互作用
- 既存の `auto_import_models` 関数は維持（後方互換性）
- `MineDbConfig` に新しい設定を追加
- Alembic のマイグレーションプロセスに統合

### 完全な実装例

```python
# repom/utility.py に追加

def auto_import_models_by_package(
    package_name: str,
    excluded_dirs: Optional[Set[str]] = None
) -> None:
    """
    パッケージ名からモデルを自動インポート
    
    Args:
        package_name: Python パッケージ名（例: 'myapp.models'）
        excluded_dirs: 除外するディレクトリ名のセット
    
    Example:
        auto_import_models_by_package('myapp.models')
        auto_import_models_by_package('shared.models')
    
    Raises:
        ImportError: パッケージが見つからない場合
        ValueError: パッケージではなくモジュールの場合
    """
    try:
        package = importlib.import_module(package_name)
        if not hasattr(package, '__path__'):
            raise ValueError(f"{package_name} is not a package (it's a module)")
        
        package_dir = Path(package.__path__[0])
        
        auto_import_models(
            models_dir=package_dir,
            base_package=package_name,
            excluded_dirs=excluded_dirs
        )
    except ImportError as e:
        raise ImportError(f"Failed to import package {package_name}: {e}")


def auto_import_models_from_list(
    package_names: List[str],
    excluded_dirs: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> Dict[str, Optional[Exception]]:
    """
    複数のパッケージからモデルを自動インポート
    
    Args:
        package_names: パッケージ名のリスト
        excluded_dirs: 除外するディレクトリ名のセット
        fail_on_error: エラー時に例外を発生させるか
    
    Returns:
        Dict[str, Optional[Exception]]: パッケージ名とエラーのマッピング
                                        成功した場合は None
    
    Example:
        auto_import_models_from_list([
            'myapp.models',
            'shared.models',
            'plugins.payment.models'
        ])
    """
    results = {}
    for package_name in package_names:
        try:
            auto_import_models_by_package(package_name, excluded_dirs)
            results[package_name] = None
        except Exception as e:
            results[package_name] = e
            if fail_on_error:
                raise
            else:
                print(f"Warning: Failed to import models from {package_name}: {e}")
    return results


# repom/config.py に追加

class MineDbConfig:
    # ... 既存の設定 ...
    
    # モデルの自動インポート設定
    MODEL_LOCATIONS: List[str] = field(default_factory=lambda: 
        os.getenv('MODEL_LOCATIONS', '').split(',') if os.getenv('MODEL_LOCATIONS') else []
    )
    
    MODEL_EXCLUDED_DIRS: Set[str] = field(default_factory=lambda: {
        'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'
    })
    
    @classmethod
    def auto_import_all_models(cls) -> Dict[str, Optional[Exception]]:
        """
        設定されたすべてのモデルパッケージからモデルをインポート
        
        Returns:
            Dict[str, Optional[Exception]]: インポート結果
        """
        from repom.utility import auto_import_models_from_list
        
        if not cls.MODEL_LOCATIONS:
            print("Warning: MODEL_LOCATIONS is empty. No models will be imported.")
            return {}
        
        return auto_import_models_from_list(
            package_names=cls.MODEL_LOCATIONS,
            excluded_dirs=cls.MODEL_EXCLUDED_DIRS,
            fail_on_error=False  # 開発時は警告のみ
        )


# alembic/env.py での使用

from repom.config import CONFIG
from repom.db import Base

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    # モデルを自動インポート
    import_results = CONFIG.auto_import_all_models()
    
    # エラーがあればログ出力
    errors = {pkg: err for pkg, err in import_results.items() if err is not None}
    if errors:
        print(f"Warning: Failed to import some model packages: {errors}")
    
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # モデルを自動インポート
    import_results = CONFIG.auto_import_all_models()
    
    # エラーがあればログ出力
    errors = {pkg: err for pkg, err in import_results.items() if err is not None}
    if errors:
        print(f"Warning: Failed to import some model packages: {errors}")
    
    # ... 以降の処理 ...
```

### 使用例

```python
# 1. 環境変数で設定
export MODEL_LOCATIONS="myapp.models,shared.models,plugins.payment.models"
poetry run alembic revision --autogenerate -m "add models"

# 2. Python コードで設定
# config.py または env.py
from repom.config import CONFIG

CONFIG.MODEL_LOCATIONS = [
    'myapp.models',
    'shared.models',
    'plugins.payment.models'
]

# 3. 直接呼び出し
from repom.utility import auto_import_models_from_list

auto_import_models_from_list([
    'myapp.models',
    'shared.models'
])
```

## 次のステップ

- [ ] `auto_import_models_by_package` 関数の実装
- [ ] `auto_import_models_from_list` 関数の実装
- [ ] `MineDbConfig` への `MODEL_LOCATIONS` 追加
- [ ] `alembic/env.py` の修正
- [ ] 単体テストの作成
- [ ] 統合テストの作成（複数パッケージ）
- [ ] エラーハンドリングのテスト
- [ ] ドキュメントの更新
- [ ] 使用例の追加
- [ ] 実装する場合は `docs/research/` に移動

## 関連ドキュメント

- `repom/utility.py` - 既存の `auto_import_models` 関数
- `repom/config.py` - 設定クラス
- `alembic/env.py` - Alembic 実行環境
- `docs/guides/repository_and_utilities_guide.md` - `auto_import_models` ガイド

## 解決すべき質問

1. 環境変数での設定 vs Python コードでの設定、どちらを推奨するか？
2. インポート失敗時のデフォルト動作は？（警告 vs エラー）
3. キャッシュメカニズムは必要か？
4. モデルのインポート順序は重要か？（依存関係がある場合）
5. プラグイン/拡張モデルの動的な追加/削除をサポートすべきか？
6. パッケージが存在しない場合のフォールバック動作は？
7. テスト環境でのモデルインポート制御はどうするか？

## 追加アイディア

### プリセット設定
```python
# よく使う構成をプリセット化
class MineDbConfig:
    MODEL_LOCATION_PRESETS = {
        'minimal': ['myapp.models'],
        'full': ['myapp.models', 'shared.models', 'plugins.models'],
        'test': ['myapp.models', 'tests.fixtures.models'],
    }
    
    @classmethod
    def use_preset(cls, preset_name: str):
        """プリセット設定を適用"""
        cls.MODEL_LOCATIONS = cls.MODEL_LOCATION_PRESETS[preset_name]
```

### 条件付きインポート
```python
# 条件に基づいてモデルをインポート
CONFIG.MODEL_LOCATIONS = [
    'myapp.models',  # 常にインポート
]

if CONFIG.ENABLE_PAYMENT:
    CONFIG.MODEL_LOCATIONS.append('plugins.payment.models')

if CONFIG.ENABLE_ANALYTICS:
    CONFIG.MODEL_LOCATIONS.append('plugins.analytics.models')
```

### インポート統計
```python
# インポート結果の詳細情報を取得
results = CONFIG.auto_import_all_models()

for package, error in results.items():
    if error is None:
        print(f"✓ {package}: Success")
    else:
        print(f"✗ {package}: {error}")
```

### デバッグモード
```python
# デバッグ情報を出力
CONFIG.MODEL_IMPORT_DEBUG = True

# 各モデルファイルのインポート状況を詳細に表示
# ✓ myapp.models.user: User, UserProfile
# ✓ myapp.models.product: Product, Category
# ✗ myapp.models.payment: ImportError - missing dependency
```
