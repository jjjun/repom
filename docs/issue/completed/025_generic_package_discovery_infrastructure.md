# Issue #024: 汎用パッケージディスカバリーインフラの実装

**ステータス**: 🔴 未着手

**作成日**: 2026-01-30

**優先度**: 高

**複雑度**: 中

## 問題の説明

### 現状の課題

repom の `load_models()` および `auto_import_models_*()` は**モデル専用**に特殊化されており、他の用途（ルーター、タスク、プラグインなど）で再利用できません。

このため、fast-domain などの消費側プロジェクトでは、似たようなディスカバリーロジックを**独自に実装する必要がある**状況です：

```python
# fast-domain/routes.py（独自実装）
if isinstance(self.router_paths, str):
    if ',' in self.router_paths:
        paths = [s.strip() for s in self.router_paths.split(',') if s.strip()]
    # ...

# fast-domain/config.py（独自実装）
if isinstance(self.task_directories, str):
    if ',' in self.task_directories:
        return [s.strip() for s in self.task_directories.split(',') if s.strip()]
    # ...

# 同じロジックが3箇所以上に重複
```

**問題点**:
- ✅ repom は汎用ライブラリなのに、モデル専用機能しか提供していない
- ✅ パス正規化、エラー構造化、セキュリティ検証が消費側で重複実装される
- ✅ コードの重複により、バグ混入リスクが増加

### repom のミッション

repom は **SQLAlchemy 基盤を提供する汎用ライブラリ** であり、特定のフレームワーク（FastAPI など）に依存すべきではありません。

したがって、以下の方針が適切です：

1. **汎用的な「パッケージディスカバリー」インフラを提供**
   - パス正規化
   - エラー構造化
   - セキュリティ検証

2. **現在の `load_models()` はこのインフラの利用例の1つ**
   - モデルローダーは特別ではなく、汎用インフラを使った実装例

3. **消費側プロジェクトが同じインフラを使って独自ローダーを実装**
   - fast-domain: ルーターローダー、タスクローダー
   - mine-py: プラグインローダー
   - 他: 任意のディスカバリーロジック

## 提案される解決策

### 設計方針

**repom が提供するもの**:
- 🟢 汎用的なパッケージディスカバリー基盤（"インフラ"）
- 🟢 構造化されたエラーハンドリング
- 🟢 セキュリティ検証機能

**repom が提供しないもの**:
- ⚫ "ルーター"や"タスク"といった特定用途のローダー（これは消費側の責任）
- ⚫ FastAPI 固有の機能（フレームワーク非依存を維持）

### 実装する機能

#### 1. `normalize_paths()` - パス正規化

**目的**: 文字列/リスト/カンマ区切りを統一的に処理

```python
def normalize_paths(
    paths: str | list[str] | None,
    separator: str = ','
) -> list[str]:
    """パス文字列を正規化してリストに変換
    
    Args:
        paths: パス文字列、またはパスのリスト
        separator: 区切り文字（デフォルト: カンマ）
        
    Returns:
        正規化されたパスのリスト
        
    Example:
        >>> normalize_paths("path1,path2,path3")
        ['path1', 'path2', 'path3']
        
        >>> normalize_paths(["path1", "path2"])
        ['path1', 'path2']
        
        >>> normalize_paths(None)
        []
        
        >>> normalize_paths("  path1  , path2  ,  ")
        ['path1', 'path2']  # 空白除去、空文字列除外
    """
    if not paths:
        return []
    
    if isinstance(paths, str):
        if separator in paths:
            return [s.strip() for s in paths.split(separator) if s.strip()]
        return [paths]
    
    return list(paths)
```

**使用例**:

```python
# repom 内部（load_models の改善）
from repom.utility import normalize_paths

def load_models(context: Optional[str] = None) -> None:
    # 設定値を正規化
    locations = normalize_paths(config.model_locations)
    
    for location in locations:
        # インポート処理...
```

```python
# fast-domain（ルーターローダー）
from repom.utility import normalize_paths

def get_router_paths(self) -> list[str]:
    paths = normalize_paths(self.router_paths)
    
    # 自動追加ロジック
    if self.auth.enable:
        paths.append("fast_domain.auth")
    
    return paths
```

#### 2. `DiscoveryFailure` - 構造化失敗情報

**目的**: ディスカバリー失敗を統一的に記録（モデル/ルーター/タスク問わず）

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class DiscoveryFailure:
    """汎用的なディスカバリー失敗情報
    
    あらゆる種類のディスカバリー失敗（モデル、ルーター、タスク、プラグインなど）を
    構造化して記録するためのデータクラス。
    
    Attributes:
        target: 失敗したターゲット（パッケージ名、モジュール名、ディレクトリ、ファイルなど）
        target_type: ターゲットの種類（"package", "module", "directory", "file"）
        exception_type: 発生した例外の型名
        message: エラーメッセージ
        
    Example:
        >>> failure = DiscoveryFailure(
        ...     target="myapp.routes",
        ...     target_type="package",
        ...     exception_type="ImportError",
        ...     message="No module named 'myapp.routes'"
        ... )
        >>> failure.to_dict()
        {
            'target': 'myapp.routes',
            'target_type': 'package',
            'exception_type': 'ImportError',
            'message': "No module named 'myapp.routes'"
        }
    """
    
    target: str
    target_type: Literal["package", "module", "directory", "file"]
    exception_type: str
    message: str
    
    def to_dict(self) -> dict[str, str]:
        """辞書形式に変換（ロギング用）"""
        return {
            "target": self.target,
            "target_type": self.target_type,
            "exception_type": self.exception_type,
            "message": self.message,
        }
```

**使用例**:

```python
# repom 内部（load_models の改善）
from repom.utility import DiscoveryFailure

failures: list[DiscoveryFailure] = []

for package_name in locations:
    try:
        importlib.import_module(package_name)
    except Exception as exc:
        failure = DiscoveryFailure(
            target=package_name,
            target_type="package",
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        failures.append(failure)
        logger.warning(f"Failed to load model package: {failure.target}", extra={"failure": failure.to_dict()})
```

```python
# fast-domain（ルーターローダー）
from repom.utility import DiscoveryFailure

for package_name in router_paths:
    try:
        module = importlib.import_module(package_name)
        # ルーター処理...
    except Exception as exc:
        failure = DiscoveryFailure(
            target=package_name,
            target_type="package",
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        logger.error(f"✗ Router discovery failed: {failure.target}", extra={"failure": failure.to_dict()})
```

#### 3. `DiscoveryError` - 構造化例外

**目的**: 複数の失敗を集約して単一の例外として発生

```python
from typing import Sequence

class DiscoveryError(RuntimeError):
    """汎用的なディスカバリーエラー
    
    複数のディスカバリー失敗を集約して、単一の例外として発生させる。
    
    Attributes:
        failures: DiscoveryFailure のタプル
        
    Example:
        >>> failures = [
        ...     DiscoveryFailure("myapp.routes", "package", "ImportError", "Not found"),
        ...     DiscoveryFailure("myapp.api", "package", "ModuleNotFoundError", "No module"),
        ... ]
        >>> raise DiscoveryError(failures)
        DiscoveryError: Discovery failed with 2 error(s): package 'myapp.routes' failed with ImportError: Not found; package 'myapp.api' failed with ModuleNotFoundError: No module
    """
    
    def __init__(self, failures: Sequence[DiscoveryFailure]):
        self.failures = tuple(failures)
        message = self._build_message()
        super().__init__(message)
    
    def _build_message(self) -> str:
        """エラーメッセージを生成"""
        details = "; ".join(
            f"{failure.target_type} '{failure.target}' failed with "
            f"{failure.exception_type}: {failure.message}"
            for failure in self.failures
        )
        return f"Discovery failed with {len(self.failures)} error(s): {details}"
```

**使用例**:

```python
# repom 内部（load_models の改善）
from repom.utility import DiscoveryError

if failures and config.model_import_strict:
    raise DiscoveryError(failures)
```

```python
# fast-domain（ルーターローダー）
from repom.utility import DiscoveryError

if failures:
    logger.error("Router discovery encountered failures", extra={"failures": [f.to_dict() for f in failures]})
    raise DiscoveryError(failures)
```

#### 4. `validate_package_security()` - セキュリティ検証

**目的**: パッケージ名のホワイトリスト検証（既存機能の拡張）

```python
def validate_package_security(
    package_name: str,
    allowed_prefixes: set[str],
    strict: bool = True
) -> None:
    """パッケージ名のセキュリティ検証
    
    許可されたプレフィックスで始まるパッケージのみを受け入れる。
    これにより、任意のコード実行を防ぐ。
    
    Args:
        package_name: 検証するパッケージ名
        allowed_prefixes: 許可されたプレフィックスのセット
        strict: 厳格モード（デフォルト: True）
                False の場合は警告のみ
        
    Raises:
        ValueError: パッケージが許可リストにない場合（strict=True）
        
    Example:
        >>> validate_package_security(
        ...     "myapp.routes",
        ...     allowed_prefixes={'myapp.', 'shared.', 'fast_domain.'}
        ... )
        # OK
        
        >>> validate_package_security(
        ...     "malicious.code",
        ...     allowed_prefixes={'myapp.', 'shared.'}
        ... )
        ValueError: Security: Package 'malicious.code' is not in allowed list
        
        >>> validate_package_security(
        ...     "malicious.code",
        ...     allowed_prefixes={'myapp.'},
        ...     strict=False
        ... )
        # 警告ログのみ
    """
    if not any(package_name.startswith(prefix) for prefix in allowed_prefixes):
        message = (
            f"Security: Package '{package_name}' is not in allowed list. "
            f"Allowed prefixes: {allowed_prefixes}"
        )
        
        if strict:
            raise ValueError(message)
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(message)
```

**使用例**:

```python
# repom 内部（auto_import_models_by_package の改善）
from repom.utility import validate_package_security

def auto_import_models_by_package(package_name: str, allowed_prefixes: set[str]) -> None:
    # セキュリティ検証（既存コードを関数化）
    validate_package_security(package_name, allowed_prefixes, strict=True)
    
    # インポート処理...
```

```python
# fast-domain（ルーターローダー）
from repom.utility import validate_package_security

for package_name in router_paths:
    # セキュリティ検証
    validate_package_security(
        package_name,
        allowed_prefixes={'fast_domain.', 'myapp.', 'shared.'},
        strict=False  # 警告のみ（互換性のため）
    )
    
    # ルーター処理...
```

## 影響範囲

### 変更されるファイル

1. **repom/utility.py**
   - 新規追加: `normalize_paths()`
   - 新規追加: `DiscoveryFailure` クラス
   - 新規追加: `DiscoveryError` クラス
   - 新規追加: `validate_package_security()`
   - 既存改善: `auto_import_models_by_package()` - 新関数を使うようリファクタリング
   - 既存改善: `load_models()` - 新関数を使うようリファクタリング

2. **tests/unit_tests/test_utility.py**
   - 新規テスト: `TestNormalizePaths`
   - 新規テスト: `TestDiscoveryFailure`
   - 新規テスト: `TestDiscoveryError`
   - 新規テスト: `TestValidatePackageSecurity`

### 影響を受ける機能

**既存機能への影響（後方互換性維持）**:
- ✅ `load_models()` - 内部実装のみ変更、インターフェース変更なし
- ✅ `auto_import_models_by_package()` - セキュリティ検証部分を関数化、動作変更なし

**新機能の提供**:
- ✅ 消費側プロジェクト（fast-domain など）が汎用インフラを使ってカスタムローダーを実装可能

## 実装計画

### Phase 1: 汎用ヘルパーの追加（コア機能）

1. **`normalize_paths()` の実装**
   - 実装: `repom/utility.py`
   - テスト: `tests/unit_tests/test_utility.py`
   - 対象: 文字列/リスト/カンマ区切りの統一処理

2. **`DiscoveryFailure` / `DiscoveryError` の実装**
   - 実装: `repom/utility.py`
   - テスト: `tests/unit_tests/test_utility.py`
   - 対象: 構造化エラーハンドリング

3. **`validate_package_security()` の実装**
   - 実装: `repom/utility.py`
   - テスト: `tests/unit_tests/test_utility.py`
   - 対象: セキュリティ検証の関数化

### Phase 2: 既存コードのリファクタリング

4. **`auto_import_models_by_package()` の改善**
   - セキュリティ検証部分を `validate_package_security()` に置き換え
   - エラーハンドリングを `DiscoveryFailure` に統一

5. **`load_models()` の改善**
   - パス正規化を `normalize_paths()` に置き換え
   - エラーハンドリングを `DiscoveryError` に統一

### Phase 3: ドキュメント更新

6. **ガイドの作成**
   - `docs/guides/features/package_discovery_guide.md` を作成
   - 汎用インフラの使い方
   - カスタムローダーの実装例（ルーター、タスク、プラグインなど）

7. **README の更新**
   - 新機能の説明を追加
   - fast-domain での使用例を紹介

## テスト計画

### 単体テスト

```python
# tests/unit_tests/test_utility.py

class TestNormalizePaths:
    """normalize_paths() のテスト"""
    
    def test_single_string(self):
        assert normalize_paths("path1") == ["path1"]
    
    def test_comma_separated(self):
        assert normalize_paths("path1,path2,path3") == ["path1", "path2", "path3"]
    
    def test_list(self):
        assert normalize_paths(["path1", "path2"]) == ["path1", "path2"]
    
    def test_none(self):
        assert normalize_paths(None) == []
    
    def test_empty_string(self):
        assert normalize_paths("") == []
    
    def test_strip_whitespace(self):
        assert normalize_paths("  path1  , path2  ,  ") == ["path1", "path2"]
    
    def test_custom_separator(self):
        assert normalize_paths("path1;path2;path3", separator=';') == ["path1", "path2", "path3"]


class TestDiscoveryFailure:
    """DiscoveryFailure のテスト"""
    
    def test_to_dict(self):
        failure = DiscoveryFailure(
            target="myapp.routes",
            target_type="package",
            exception_type="ImportError",
            message="Not found"
        )
        assert failure.to_dict() == {
            "target": "myapp.routes",
            "target_type": "package",
            "exception_type": "ImportError",
            "message": "Not found"
        }
    
    def test_frozen(self):
        failure = DiscoveryFailure("test", "package", "Error", "message")
        with pytest.raises(AttributeError):
            failure.target = "modified"


class TestDiscoveryError:
    """DiscoveryError のテスト"""
    
    def test_single_failure(self):
        failures = [
            DiscoveryFailure("myapp.routes", "package", "ImportError", "Not found")
        ]
        error = DiscoveryError(failures)
        assert "Discovery failed with 1 error(s)" in str(error)
        assert "myapp.routes" in str(error)
    
    def test_multiple_failures(self):
        failures = [
            DiscoveryFailure("myapp.routes", "package", "ImportError", "Not found"),
            DiscoveryFailure("myapp.api", "package", "ModuleNotFoundError", "No module")
        ]
        error = DiscoveryError(failures)
        assert "Discovery failed with 2 error(s)" in str(error)
        assert "myapp.routes" in str(error)
        assert "myapp.api" in str(error)
    
    def test_failures_tuple(self):
        failures = [DiscoveryFailure("test", "package", "Error", "msg")]
        error = DiscoveryError(failures)
        assert isinstance(error.failures, tuple)
        assert len(error.failures) == 1


class TestValidatePackageSecurity:
    """validate_package_security() のテスト"""
    
    def test_allowed_package(self):
        # 例外が発生しないことを確認
        validate_package_security(
            "myapp.routes",
            allowed_prefixes={'myapp.', 'shared.'}
        )
    
    def test_allowed_exact_match(self):
        # プレフィックス完全一致
        validate_package_security(
            "myapp.models.user",
            allowed_prefixes={'myapp.'}
        )
    
    def test_disallowed_package_strict(self):
        with pytest.raises(ValueError) as exc:
            validate_package_security(
                "malicious.code",
                allowed_prefixes={'myapp.', 'shared.'},
                strict=True
            )
        assert "Security" in str(exc.value)
        assert "malicious.code" in str(exc.value)
    
    def test_disallowed_package_non_strict(self, caplog):
        # 警告ログが出力されることを確認
        validate_package_security(
            "malicious.code",
            allowed_prefixes={'myapp.', 'shared.'},
            strict=False
        )
        assert "Security" in caplog.text
        assert "malicious.code" in caplog.text
    
    def test_empty_allowed_prefixes(self):
        with pytest.raises(ValueError):
            validate_package_security(
                "myapp.routes",
                allowed_prefixes=set(),
                strict=True
            )
```

### 統合テスト

```python
# tests/unit_tests/test_utility_integration.py

class TestLoadModelsWithNewInfra:
    """load_models() が新インフラを使っているか確認"""
    
    def test_load_models_uses_normalize_paths(self, monkeypatch):
        # config.model_locations がカンマ区切り文字列でも動作するか
        monkeypatch.setattr(config, 'model_locations', 'repom.examples.models,other.models')
        
        # load_models() が正常に動作
        load_models()
    
    def test_load_models_strict_mode(self, monkeypatch):
        # 不正なパッケージでエラーが発生するか
        monkeypatch.setattr(config, 'model_locations', ['invalid.package'])
        monkeypatch.setattr(config, 'model_import_strict', True)
        
        with pytest.raises(DiscoveryError) as exc:
            load_models()
        
        assert len(exc.value.failures) == 1
        assert "invalid.package" in str(exc.value)
```

## 期待される効果

### 1. コードの重複削減

**Before（fast-domain 内に3箇所で重複）**:
```python
# routes.py, config.py, invoke/loader.py で同じロジック
if isinstance(paths, str):
    if ',' in paths:
        paths = [s.strip() for s in paths.split(',') if s.strip()]
    # ...
```

**After（repom の汎用関数を使用）**:
```python
from repom.utility import normalize_paths

paths = normalize_paths(self.router_paths)
dirs = normalize_paths(self.task_directories)
```

### 2. エラーハンドリングの統一

**Before（各ローダーで独自実装）**:
- モデルローダー: エラー集約なし
- ルーターローダー: `RouterDiscoveryFailure` / `RouterDiscoveryError`
- タスクローダー: `TaskDiscoveryFailure` / `TaskDiscoveryError`

**After（repom で統一）**:
```python
from repom.utility import DiscoveryFailure, DiscoveryError

# すべてのローダーで同じクラスを使用
```

### 3. セキュリティ機能の共有

**Before（モデルローダーのみ）**:
- セキュリティ検証はモデルローダーだけ

**After（すべてのローダーで）**:
```python
from repom.utility import validate_package_security

# ルーター、タスク、プラグインローダーでもセキュリティチェック可能
validate_package_security(package_name, allowed_prefixes)
```

### 4. 他プロジェクトでの再利用性

```python
# mine-py でプラグインローダーを実装
from repom.utility import normalize_paths, DiscoveryFailure, DiscoveryError, validate_package_security

plugin_paths = normalize_paths(config.plugin_paths)

for plugin in plugin_paths:
    validate_package_security(plugin, allowed_prefixes={'mine_py.plugins.'})
    # プラグイン読み込み...
```

## 関連ドキュメント

- **fast-domain/docs/issue/repom_request_generic_discovery_helpers.md**: 元の要望ドキュメント
- **docs/guides/features/auto_import_models_guide.md**: 現在のモデル自動インポート機能
- **docs/technical/hybrid_package_logging_strategy.md**: ロギング戦略（参考）

## 完了基準

- ✅ `normalize_paths()` の実装とテスト（5件以上のテストケース）
- ✅ `DiscoveryFailure` / `DiscoveryError` の実装とテスト（3件以上のテストケース）
- ✅ `validate_package_security()` の実装とテスト（4件以上のテストケース）
- ✅ `auto_import_models_by_package()` のリファクタリング
- ✅ `load_models()` のリファクタリング
- ✅ すべての既存テストが通過（後方互換性維持）
- ✅ 新規ガイドの作成（`docs/guides/features/package_discovery_guide.md`）
- ✅ README の更新

---

**要望元**: fast-domain プロジェクト  
**関連Issue**: fast-domain/docs/issue/repom_request_generic_discovery_helpers.md
