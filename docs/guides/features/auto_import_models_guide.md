# SQLAlchemy モデル自動インポートガイド

## 概要

repom は **汎用パッケージディスカバリーインフラ** ([discovery_guide.md](discovery_guide.md)) を使用して、SQLAlchemy モデルを自動的にインポートし、Alembic マイグレーションやデータベース作成時に `Base.metadata` に登録します。

**主な機能**:
- 指定ディレクトリまたはパッケージから Python ファイルを再帰的に検索
- SQLAlchemy モデルクラスを動的にインポート
- 除外ディレクトリの設定によるフィルタリング
- **セキュリティ検証**: 許可されたパッケージのみインポート可能
- **循環参照対応**: `post_import_hook` で `configure_mappers()` を実行

> **Note**: このガイドは SQLAlchemy 統合に特化しています。汎用的なパッケージディスカバリーについては [discovery_guide.md](discovery_guide.md) を参照してください。

---

## 利用可能な関数

### 1. `auto_import_models(models_dir, base_package, excluded_dirs=None)`

**目的**: ディレクトリパスからモデルを再帰的にインポート

**パラメータ**:
- `models_dir` (str | Path): モデルが格納されているディレクトリのパス
- `base_package` (str): ベースパッケージ名（例: `'myapp.models'`）
- `excluded_dirs` (Optional[Set[str]]): 除外するディレクトリ名のセット（デフォルト: `DEFAULT_EXCLUDED_DIRS`）

**使用例**:
```python
from repom.utility import auto_import_models
from pathlib import Path

# models/__init__.py で使用
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='myapp.models',
    excluded_dirs={'tests', 'migrations'}
)
```

**動作**:
- `*.py` ファイルを `rglob()` で再帰検索
- 除外ディレクトリに該当するファイルはスキップ
- アンダースコアで始まるファイル（`__init__.py`、`_private.py` など）をスキップ
- ファイルをアルファベット順にソートして一貫したインポート順序を保証
- `importlib.import_module()` でモジュールをインポート
- インポートエラーは `DiscoveryFailure` として返却（`fail_on_error=False` の場合）

---

### 2. `import_package_directory(package_name, excluded_dirs=None, allowed_prefixes=None, fail_on_error=False)`

**目的**: パッケージ名からディレクトリを自動検出してインポート（セキュリティ検証付き）

**パラメータ**:
- `package_name` (str): インポートするパッケージ名（例: `myapp.models`）
- `excluded_dirs` (Optional[Set[str]]): 除外するディレクトリ名のセット
- `allowed_prefixes` (Optional[Set[str]]): 許可するパッケージプレフィックスのセット
- `fail_on_error` (bool): エラー時に例外を送出するか（デフォルト: False）

**戻り値**: `List[DiscoveryFailure]` - 失敗したインポートのリスト

**使用例**:
```python
from repom.utility import import_package_directory

# セキュリティ検証あり
failures = import_package_directory(
    'myapp.models',
    excluded_dirs={'tests', 'base', 'mixin'},
    allowed_prefixes={'myapp.', 'repom.'}
)

if failures:
    print(f"Failed to import {len(failures)} modules")
```

**セキュリティ動作**:
- `allowed_prefixes` が設定されている場合、パッケージ名のプレフィックスを検証
- 許可リストにないパッケージは `ValueError` を送出
- `allowed_prefixes=None` の場合は検証をスキップ

**エラー例**:
```python
# 許可されていないパッケージをインポートしようとした場合
import_package_directory(
    'untrusted_package.models',
    allowed_prefixes={'myapp.', 'repom.'}
)
# ValueError: Security: Package 'untrusted_package.models' is not in allowed list. Allowed prefixes: {'myapp.', 'repom.'}
```

---

### 3. `import_from_packages(package_names, excluded_dirs=None, allowed_prefixes=None, fail_on_error=False, post_import_hook=None)`

**目的**: 複数パッケージをバッチインポート + インポート完了後のフック実行

**パラメータ**:
- `package_names` (str | List[str]): インポートするパッケージ名（カンマ区切り文字列またはリスト）
- `excluded_dirs` (Optional[Set[str]]): 除外するディレクトリ名
- `allowed_prefixes` (Optional[Set[str]]): 許可するパッケージプレフィックス
- `fail_on_error` (bool): エラー時に例外を送出するか（デフォルト: False）
- `post_import_hook` (Optional[Callable]): すべてのインポート完了後に実行する関数

**戻り値**: `List[DiscoveryFailure]` - 失敗したインポートのリスト

**使用例**:
```python
from repom.utility import import_from_packages
from sqlalchemy.orm import configure_mappers

# 複数パッケージをインポート + マッパー初期化
failures = import_from_packages(
    package_names=['myapp.models', 'myapp.modules.user', 'repom.models'],
    excluded_dirs={'tests', 'migrations', 'base', 'mixin'},
    allowed_prefixes={'myapp.', 'repom.'},
    post_import_hook=configure_mappers  # 循環参照対策
)

if failures:
    for f in failures:
        print(f"Warning: {f.target} - {f.message}")
```

**エラーハンドリング**:
- `fail_on_error=False`: エラーを `DiscoveryFailure` として返却し、処理を継続
- `fail_on_error=True`: 最初のエラーで `DiscoveryError` を送出

**循環参照の解決** (Issue #020):

この関数は `post_import_hook` パラメータにより、循環参照を持つモデルを正しく処理します：

```python
from sqlalchemy.orm import configure_mappers

# すべてのパッケージをインポート後、マッパーを初期化
import_from_packages(
    package_names=['myapp.models', 'shared.models'],
    post_import_hook=configure_mappers  # すべてのインポート完了後に実行
)
```

**動作フロー**:
1. すべてのパッケージを順次インポート（モデルクラスのみ定義）
2. すべてのインポート完了後に `post_import_hook()` を実行
3. `configure_mappers()` がすべてのモデルクラスを認識した状態でマッパー初期化

**利点**:
- ✅ 循環参照エラーを透過的に解決（ユーザーコードの変更不要）
- ✅ マッパー初期化時にすべてのモデルクラスが利用可能
- ✅ `relationship()` の文字列参照が正しく解決される
- ✅ フックパターンで拡張可能（他のフレームワークでも同様に使用可能）

**例**: `ModelA` が `ModelB` を参照し、`ModelB` が `ModelA` を参照する場合でも、両方のクラスがインポートされた後にマッパー初期化されるため、エラーが発生しません。

**関連ドキュメント**: [Issue #020 - 循環参照警告の解決](../../issue/completed/020_circular_import_mapper_configuration.md)

---

## 設定による自動インポート（RepomConfig）

### 設定プロパティ

`RepomConfig` クラスに以下の設定を追加することで、`load_models()` 関数が自動的に複数パッケージからモデルをインポートします。

#### `model_locations: Optional[List[str]]`

インポートするパッケージ名のリスト。

**設定例**:
```python
from repom.config import config

config.model_locations = [
    'myapp.models',
    'myapp.modules.user',
    'myapp.modules.task'
]
```

#### `model_excluded_dirs: Optional[Set[str]]`

除外するディレクトリ名のセット。

**設定例**:
```python
config.model_excluded_dirs = {'tests', 'migrations', 'scripts'}
```

**未設定の場合**: `DEFAULT_EXCLUDED_DIRS` が使用されます。
```python
DEFAULT_EXCLUDED_DIRS = {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}
```

#### `allowed_package_prefixes: Set[str]`

インポートを許可するパッケージプレフィックスのセット（セキュリティ対策）。

**デフォルト値**: `{'repom.'}`

**設定例**:
```python
config.allowed_package_prefixes = {'myapp.', 'repom.', 'shared.'}
```

**重要**: 親プロジェクトでこの設定を明示的に追加する必要があります。デフォルトでは `repom.` パッケージのみが許可されています。

**セキュリティ検証のスキップ**: `allowed_prefixes=None` を指定することで、セキュリティ検証をスキップできます。ただし、本番環境では推奨されません。

#### `model_import_strict: bool`

モデルインポート失敗時に例外を送出するかどうか。

**デフォルト値**: `False`（警告のみで処理を継続）

**設定例**:
```python
# 開発環境では厳格にエラーを検出
config.model_import_strict = True

# 本番環境では柔軟に対応（デフォルト）
config.model_import_strict = False
```

**動作**:
- `False`: インポート失敗時に警告メッセージを出力して継続（タイポに気づきにくい）
- `True`: インポート失敗時に `ImportError` を送出して停止（早期発見）

---

### CONFIG_HOOK での設定

親プロジェクトで `CONFIG_HOOK` を使用して設定をカスタマイズできます。

**例: `myapp/config_hook.py`**:
```python
from repom.config import RepomConfig

class MyAppConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # 複数パッケージからモデルをインポート
        self.model_locations = [
            'myapp.models',           # アプリケーションのメインモデル
            'myapp.modules.user',     # ユーザーモジュール
            'myapp.modules.task',     # タスクモジュール
            'repom.models'            # repom の共有モデル
        ]
        
        # 除外ディレクトリを追加
        self.model_excluded_dirs = {'tests', 'migrations', 'scripts', 'tmp'}
        
        # 許可するパッケージプレフィックスを設定（セキュリティ重要）
        self.allowed_package_prefixes = {'myapp.', 'repom.', 'shared.'}
        
        # 開発環境では厳格モード（オプション）
        import os
        if os.getenv('EXEC_ENV') in ['dev', 'test']:
            self.model_import_strict = True

def get_repom_config():
    return MyAppConfig()
```

**環境変数で CONFIG_HOOK を指定**:
```bash
# .env ファイル
CONFIG_HOOK=myapp.config_hook:get_repom_config
```

---

## セキュリティに関する重要事項

### なぜセキュリティ検証が必要か

`importlib.import_module()` は任意のパッケージをインポートできるため、以下のリスクがあります:

1. **任意コード実行**: 信頼できないパッケージをインポートすると、そのモジュールレベルのコードが実行される
2. **依存関係の混入**: 意図しないパッケージの依存関係が環境に影響を与える
3. **設定ミス**: タイポや設定ミスで予期しないモジュールがインポートされる

### 許可リスト方式

`allowed_package_prefixes` は**許可リスト方式**でセキュリティを強化します:

```python
# ⚠️ セキュリティ検証をスキップ（直接関数を呼ぶ場合のみ可能）
auto_import_models_by_package(
    'any_package.models',
    allowed_prefixes=None  # 検証をスキップ
)

# ✅ 安全: 明示的に許可されたパッケージのみ
config.allowed_package_prefixes = {'myapp.', 'repom.'}

# ❌ エラー: 許可されていないパッケージ
config.model_locations = ['untrusted_package.models']  # ValueError
```

**注意**: `load_models()` 経由では常に `config.allowed_package_prefixes` が使用されるため、`None` によるスキップはできません。直接 `auto_import_models_by_package()` を呼ぶ場合のみ `allowed_prefixes=None` でスキップ可能です。

### デフォルト設定の意図

**デフォルト**: `{'repom.'}`

これは、親プロジェクトが明示的に `allowed_package_prefixes` を設定しない限り、`repom` パッケージ以外のインポートが拒否されることを意味します。

**理由**:
- 設定ミスによる意図しないインポートを防ぐ
- セキュリティ意識を高める（明示的な設定を要求）
- デフォルトで安全な動作を保証

---

## load_models() の動作

### 概要

`load_models()` 関数は、データベース作成、マイグレーション、テストなどのタイミングで呼び出され、SQLAlchemy モデルを `Base.metadata` に登録します。

### 動作フロー

```python
def load_models(context: Optional[str] = None) -> None:
    """モデルを読み込む（RepomConfig の設定に基づく）"""
    from repom.config import config
    from repom.utility import import_from_packages
    from sqlalchemy.orm import configure_mappers

    if config.model_locations:
        # 複数パッケージからインポート + マッパー初期化
        import_from_packages(
            package_names=config.model_locations,
            excluded_dirs=config.model_excluded_dirs,
            allowed_prefixes=config.allowed_package_prefixes,
            fail_on_error=config.model_import_strict,
            post_import_hook=configure_mappers  # 循環参照対策
        )
    else:
        # 後方互換性: デフォルト動作（repom.examples.models を直接インポート）
        from repom.examples import models  # noqa: F401
```

### 後方互換性

`config.model_locations` が設定されていない場合、従来の動作（`from repom import models`）にフォールバックします。

**既存プロジェクトへの影響**: なし（設定を変更しない限り、従来通りの動作）

---

## 使用パターン

### パターン1: シンプルな単一パッケージ

```python
# config_hook.py
from repom.config import RepomConfig

class MyAppConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        self.model_locations = ['myapp.models']
        self.allowed_package_prefixes = {'myapp.', 'repom.'}

def get_repom_config():
    return MyAppConfig()
```

### パターン2: 複数モジュールに分散したモデル

```python
# config_hook.py
from repom.config import RepomConfig

class MyAppConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        self.model_locations = [
            'myapp.core.models',
            'myapp.auth.models',
            'myapp.api.models',
            'repom.models'
        ]
        self.model_excluded_dirs = {'tests', 'migrations'}
        self.allowed_package_prefixes = {'myapp.', 'repom.'}

def get_repom_config():
    return MyAppConfig()
```

### パターン3: 環境別の設定

```python
# config_hook.py
import os
from repom.config import RepomConfig

class MyAppConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        if os.getenv('EXEC_ENV') == 'test':
            # テスト環境: テストモデルも含める
            self.model_locations = [
                'myapp.models',
                'myapp.test_models'
            ]
        else:
            # 本番環境: テストモデルを除外
            self.model_locations = ['myapp.models']
        
        self.allowed_package_prefixes = {'myapp.', 'repom.'}
        
        # 開発/テスト環境では厳格モード
        self.model_import_strict = os.getenv('EXEC_ENV') in ['dev', 'test']

def get_repom_config():
    return MyAppConfig()
```

---

## トラブルシューティング

### ValueError: Security: Package '...' is not in allowed list

**原因**: インポートしようとしたパッケージが `allowed_package_prefixes` に含まれていない

**解決方法**:
```python
# config_hook.py で許可リストを追加
config.allowed_package_prefixes = {'myapp.', 'repom.', 'newpackage.'}
```

### ModuleNotFoundError: No module named '...'

**原因**: パッケージ名が間違っているか、パッケージがインストールされていない

**解決方法**:
1. パッケージ名のスペルを確認
2. パッケージがインストールされているか確認（`poetry show` or `pip list`）
3. `PYTHONPATH` が正しく設定されているか確認

### モデルが Alembic で検出されない

**原因**: モデルが `Base.metadata` に登録されていない

**解決方法**:
1. `config.model_locations` にパッケージが含まれているか確認
2. モデルファイルが除外ディレクトリに含まれていないか確認
3. SQLAlchemy の `Base` を継承しているか確認
4. デバッグ: `load_models()` を直接呼び出してエラーを確認

### インポート失敗が通知されない

**原因**: `fail_on_error=False`（デフォルト）の場合、エラーは `DiscoveryFailure` として返却されるだけ

**解決方法**:
```python
# 開発環境では厳格モードを有効化
config.model_import_strict = True  # fail_on_error=True に設定される
```

---

## AI エージェント向けノート

### コード生成時の注意点

1. **セキュリティ第一**: `model_locations` を設定する場合、必ず `allowed_package_prefixes` も設定する
2. **デフォルト値を変更しない**: `allowed_package_prefixes` のデフォルトは `{'repom.'}` のまま維持
3. **後方互換性を維持**: `config.model_locations` が `None` の場合、従来の動作を保証
4. **エラーメッセージの明確化**: セキュリティエラーは `ValueError` で、許可リストを表示

### テストコード生成時のポイント

```python
# テスト用の設定
def test_import_package_directory():
    from repom.utility import import_package_directory
    
    # セキュリティ検証のテスト
    with pytest.raises(ValueError, match="Security"):
        import_package_directory(
            'untrusted.models',
            allowed_prefixes={'trusted.'}
        )
    
    # 正常なインポートのテスト
    failures = import_package_directory(
        'trusted.models',
        allowed_prefixes={'trusted.'}
    )
    assert len(failures) == 0
```

### ドキュメント更新のガイドライン

このガイドは SQLAlchemy モデル自動インポート機能の修正の度に更新します:

- 汎用インフラの変更: [discovery_guide.md](discovery_guide.md) を更新（このファイルは SQLAlchemy 統合の説明のみ）
- 新しい設定オプションが追加された場合: 「設定プロパティ」セクションに追加
- セキュリティ機能が変更された場合: 「セキュリティに関する重要事項」セクションを更新
- バグ修正の場合: 「トラブルシューティング」セクションに事例を追加

---

## 関連ドキュメント

- **[discovery_guide.md](discovery_guide.md)**: 汎用パッケージディスカバリーインフラ（詳細な実装解説）
- **[repository_and_utilities_guide.md](../repository/repository_and_utilities_guide.md)**: `BaseRepository` との統合
- **[AGENTS.md](../../../AGENTS.md)**: プロジェクト構造とコマンドリファレンス
- **[Issue #020](../../issue/completed/020_circular_import_mapper_configuration.md)**: 循環参照警告の解決（マッパー遅延初期化）

---

**最終更新**: 2026-01-28 (Issue #020 循環参照解決の情報を追加)
