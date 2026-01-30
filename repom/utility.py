import os
import inflect
import unicodedata
import importlib
from pathlib import Path
from typing import Optional, Set, List, Literal, Sequence
from dataclasses import dataclass

"""
inflect
英語の単語の複数形、単数形、序数、冠詞などを生成するためのPythonライブラリです。
このライブラリを使用すると、英語の文法規則に基づいて単語の形態を変化させることができます。
主な機能
複数形の生成: 単語の複数形を生成します。
単数形の生成: 単語の単数形を生成します。
序数の生成: 数字を序数(1st, 2nd, 3rd など)に変換します。
冠詞の追加: 単語に適切な冠詞(a, an, the)を追加します。
"""

# Default directories to exclude from auto-import
DEFAULT_EXCLUDED_DIRS = {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}


# ========================================
# Generic Discovery Helpers
# ========================================

def normalize_paths(
    paths: str | List[str] | None,
    separator: str = ','
) -> List[str]:
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
    """
    if not paths:
        return []

    if isinstance(paths, str):
        if separator in paths:
            return [s.strip() for s in paths.split(separator) if s.strip()]
        return [paths]

    return list(paths)


@dataclass(frozen=True)
class DiscoveryFailure:
    """汎用的なディスカバリー失敗情報

    Attributes:
        target: 失敗したターゲット（パッケージ名、モジュール名など）
        target_type: ターゲットの種類
        exception_type: 発生した例外の型名
        message: エラーメッセージ
    """
    target: str
    target_type: Literal["package", "module", "directory", "file"]
    exception_type: str
    message: str

    def to_dict(self) -> dict:
        """辞書形式に変換（ロギング用）"""
        return {
            "target": self.target,
            "target_type": self.target_type,
            "exception_type": self.exception_type,
            "message": self.message,
        }


class DiscoveryError(RuntimeError):
    """汎用的なディスカバリーエラー

    複数のディスカバリー失敗を集約して例外として発生させる。
    """

    def __init__(self, failures: Sequence[DiscoveryFailure]):
        self.failures = tuple(failures)
        details = "; ".join(
            f"{f.target_type} '{f.target}' failed with {f.exception_type}: {f.message}"
            for f in self.failures
        )
        message = f"Discovery failed with {len(self.failures)} error(s): {details}"
        super().__init__(message)


def validate_package_security(
    package_name: str,
    allowed_prefixes: Set[str],
    strict: bool = True
) -> None:
    """パッケージ名のセキュリティ検証

    Args:
        package_name: 検証するパッケージ名
        allowed_prefixes: 許可されたプレフィックスのセット
        strict: 厳格モード（False の場合は警告のみ）

    Raises:
        ValueError: パッケージが許可リストにない場合（strict=True）
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


def get_plural_tablename(file_path: str) -> str:
    """
    ファイル名から拡張子を除去し、複数形に変換してテーブル名を取得する関数。

    Args:
        file_path (str): ファイルのパス

    Returns:
        str: 複数形に変換されたテーブル名
    """
    # ファイル名を取得し、拡張子を除去
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # inflect エンジンを初期化
    p = inflect.engine()

    # ファイル名を複数形に変換
    table_name = p.plural(file_name)

    return table_name


def import_packages(
    package_names: str | List[str] | None,
    allowed_prefixes: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> List[DiscoveryFailure]:
    """汎用的なパッケージインポート

    パッケージをインポートし、エラーを構造化して返します。
    モデル、ルーター、タスクなど、あらゆる用途で使用できます。

    Args:
        package_names: パッケージ名（文字列、リスト、カンマ区切り）
        allowed_prefixes: 許可されたプレフィックス（セキュリティ）
        fail_on_error: エラー時に例外を発生させるか

    Returns:
        失敗のリスト（空の場合はすべて成功）

    Raises:
        DiscoveryError: fail_on_error=True かつ失敗がある場合

    Example:
        # 基本的な使い方
        failures = import_packages(['myapp.routes', 'myapp.tasks'])
        if failures:
            print(f"Failed to import {len(failures)} packages")

        # セキュリティ検証付き
        import_packages(
            'myapp.routes,myapp.tasks',
            allowed_prefixes={'myapp.', 'shared.'}
        )

        # エラー時に例外を発生
        import_packages(
            ['myapp.routes'],
            fail_on_error=True
        )
    """
    # パスを正規化
    packages = normalize_paths(package_names)
    failures = []

    for package_name in packages:
        try:
            # セキュリティチェック
            if allowed_prefixes:
                validate_package_security(package_name, allowed_prefixes, strict=True)

            # インポート
            importlib.import_module(package_name)

        except Exception as exc:
            failure = DiscoveryFailure(
                target=package_name,
                target_type="package",
                exception_type=type(exc).__name__,
                message=str(exc)
            )
            failures.append(failure)

    # エラーハンドリング
    if failures and fail_on_error:
        raise DiscoveryError(failures)

    return failures


def normalize_text(s: str) -> str:
    """
    テキストの正規化（全角・半角・空白・小文字化）
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "").replace("　", "")
    return s.lower()


def auto_import_models(
    models_dir: str | Path,
    base_package: str,
    excluded_dirs: Optional[Set[str]] = None
) -> None:
    """
    Recursively import all Python modules in models directory, excluding utility directories.

    This function automatically discovers and imports all model files in a directory structure,
    making them available to SQLAlchemy's metadata without manual imports.

    Args:
        models_dir: Path to the models directory (can be string or Path object)
        base_package: Base package name (e.g., 'myapp.models')
        excluded_dirs: Set of directory names to exclude. Defaults to DEFAULT_EXCLUDED_DIRS
                      {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}

    Example:
        # In your models/__init__.py
        from pathlib import Path
        from repom.utility import auto_import_models

        auto_import_models(
            models_dir=Path(__file__).parent,
            base_package='myapp.models'
        )

        # With custom exclusions
        auto_import_models(
            models_dir=Path(__file__).parent,
            base_package='myapp.models',
            excluded_dirs={'base', 'mixin', 'tests'}
        )

    Directory Structure Example:
        myapp/models/
        ├── __init__.py          # Call auto_import_models here
        ├── user.py              # ✅ Imported
        ├── product.py           # ✅ Imported
        ├── base/                # ❌ Excluded
        │   └── helper.py
        └── admin/
            └── user.py          # ✅ Imported as myapp.models.admin.user

    Features:
        - Recursively scans all subdirectories
        - Skips utility directories (base, mixin, validators, etc.)
        - Skips files starting with underscore (__init__.py, _private.py)
        - Sorts files alphabetically for consistent import order
        - Handles import errors gracefully with warnings
        - Uses Python's import cache (no duplicate imports)
    """
    if excluded_dirs is None:
        excluded_dirs = DEFAULT_EXCLUDED_DIRS

    models_dir = Path(models_dir)

    # Collect all Python files to import
    py_files = []
    for py_file in models_dir.rglob('*.py'):
        # Skip __pycache__ directories
        if '__pycache__' in py_file.parts:
            continue

        # Skip files starting with underscore (like __init__.py)
        if py_file.stem.startswith('_'):
            continue

        # Skip excluded directories
        relative_path = py_file.relative_to(models_dir)
        if any(excluded_dir in relative_path.parts for excluded_dir in excluded_dirs):
            continue

        py_files.append((py_file, relative_path))

    # Sort files alphabetically to ensure consistent import order
    py_files.sort(key=lambda x: str(x[1]))

    # Import all collected files
    for py_file, relative_path in py_files:
        # Convert file path to module path (e.g., admin/user.py -> admin.user)
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        module_name = '.'.join(module_parts)

        # Import the module
        full_module_name = f'{base_package}.{module_name}' if module_name else base_package
        try:
            importlib.import_module(full_module_name)
        except Exception as e:
            # Log import errors but don't fail completely
            print(f"Warning: Failed to import {full_module_name}: {e}")


def auto_import_models_by_package(
    package_name: str,
    excluded_dirs: Optional[Set[str]] = None,
    allowed_prefixes: Optional[Set[str]] = None
) -> None:
    """
    パッケージ名からモデルを自動インポート（セキュリティ検証付き）

    Args:
        package_name: Python パッケージ名（例: 'myapp.models'）
        excluded_dirs: 除外するディレクトリ名のセット
        allowed_prefixes: 許可されたパッケージプレフィックス（セキュリティ）

    Example:
        auto_import_models_by_package('myapp.models')
        auto_import_models_by_package(
            'shared.models',
            allowed_prefixes={'myapp.', 'shared.', 'repom.'}
        )

    Raises:
        ValueError: パッケージが許可リストにない、またはパッケージではない場合
        ImportError: パッケージが見つからない場合

    Security:
        allowed_prefixes を指定することで、信頼できるパッケージのみをインポート可能。
        これにより、任意のコード実行を防ぎます。
    """
    # セキュリティチェック: 許可リストの検証（新しいヘルパーを使用）
    if allowed_prefixes:
        validate_package_security(package_name, allowed_prefixes, strict=True)

    try:
        # パッケージをインポート
        package = importlib.import_module(package_name)

        # パッケージかどうか確認（モジュールではダメ）
        if not hasattr(package, '__path__'):
            raise ValueError(f"{package_name} is not a package (it's a module)")

        # パッケージのディレクトリを取得
        package_dir = Path(package.__path__[0])

        # 既存の auto_import_models を使用してインポート
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
    allowed_prefixes: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> None:
    """
    複数のパッケージからモデルを一括インポート

    Args:
        package_names: パッケージ名のリスト
        excluded_dirs: 除外するディレクトリ名のセット
        allowed_prefixes: 許可されたパッケージプレフィックス（セキュリティ）
        fail_on_error: エラー時に例外を発生させるか（デフォルト: 警告のみ）

    Example:
        auto_import_models_from_list([
            'myapp.models',
            'shared.models',
            'plugins.payment.models'
        ], allowed_prefixes={'myapp.', 'shared.', 'plugins.', 'repom.'})

    Returns:
        None（エラーは警告として出力、または例外として発生）

    Security:
        allowed_prefixes を指定することで、信頼できるパッケージのみをインポート。

    Note:
        循環参照を持つモデルを正しく処理するため、すべてのパッケージを
        インポートした後に configure_mappers() を呼び出します。
        これにより、マッパー初期化時にすべてのモデルクラスが利用可能になります。

        See: Issue #020 - 循環参照警告の解決（マッパー遅延初期化）
    """
    from sqlalchemy.orm import configure_mappers

    # Step 1: すべてのパッケージをインポート（汎用ヘルパーを使用）
    # Note: モデルパッケージは通常のパッケージインポートではなく、
    #       auto_import_models_by_package() を使ってディレクトリ走査が必要
    for package_name in package_names:
        try:
            auto_import_models_by_package(
                package_name=package_name,
                excluded_dirs=excluded_dirs,
                allowed_prefixes=allowed_prefixes
            )
        except Exception as e:
            if fail_on_error:
                raise
            else:
                print(f"Warning: Failed to import models from {package_name}: {e}")

    # Step 2: すべてのインポート完了後にマッパーを初期化
    # これにより、循環参照を持つモデルも正しく解決される
    try:
        configure_mappers()
    except Exception as e:
        error_msg = f"Failed to configure mappers after importing all packages: {e}"
        if fail_on_error:
            raise RuntimeError(error_msg) from e
        else:
            print(f"Warning: {error_msg}")


def load_models(context: Optional[str] = None) -> None:
    """Import all application models so SQLAlchemy can discover metadata.

    This function imports models based on config.model_locations setting.
    If model_locations is not set, it falls back to importing repom.models.

    Args:
        context: Execution context for logging (e.g., "db_create", "db_delete", "alembic_migration")

    Usage:
        from repom.utility import load_models
        load_models(context="db_create")  # Import with context info

    Note:
        This function is typically called by:
        - Alembic migrations (alembic/env.py)
        - Database scripts (db_create.py, db_delete.py, etc.)
        - Test fixtures (tests/conftest.py)
    """
    from repom.config import config
    from repom.logging import get_logger

    logger = get_logger(__name__)
    context_prefix = f"[{context}] " if context else ""

    logger.debug(f"{context_prefix}Starting model loading...")

    if config.model_locations:
        auto_import_models_from_list(
            package_names=config.model_locations,
            excluded_dirs=config.model_excluded_dirs,
            allowed_prefixes=config.allowed_package_prefixes,
            fail_on_error=config.model_import_strict
        )
    else:
        # デフォルト動作（後方互換性）
        # Importing the examples package has the side-effect of registering every
        # SQLAlchemy model defined by the application.
        try:
            from repom.examples import models  # noqa: F401  # pylint: disable=unused-import
        except ImportError:
            # repom.examples.models が存在しない場合は警告のみ
            logger.warning(f"{context_prefix}No model locations configured and repom.examples.models not found.")

    # Log loaded models
    from repom.models.base_model import Base
    try:
        # Get table names from metadata (most reliable method)
        table_names = sorted(Base.metadata.tables.keys())
        logger.debug(f"{context_prefix}Loaded {len(table_names)} models: {', '.join(table_names)}")
    except Exception as e:
        logger.warning(f"{context_prefix}Could not retrieve model list: {e}")
