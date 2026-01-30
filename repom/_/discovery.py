"""
Generic Package Discovery Infrastructure

This module provides reusable helpers for discovering and importing packages,
modules, and files. These utilities are framework-agnostic and can be used
for models, routers, tasks, plugins, or any other discovery use case.

Key Features:
- Path normalization (string/list/comma-separated)
- Structured error handling (DiscoveryFailure/DiscoveryError)
- Security validation (whitelist-based)
- Generic package importing
- Directory-based module discovery
- Package-based bulk importing with hooks

Example:
    >>> from repom._.discovery import import_packages
    >>> failures = import_packages("myapp.routes,myapp.tasks")
    >>> if failures:
    ...     print(f"Failed: {[f.target for f in failures]}")
"""

import importlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Set, List, Literal, Sequence, Callable


# ========================================
# Constants
# ========================================

# 汎用的な除外ディレクトリ（フレームワーク非依存）
DEFAULT_EXCLUDED_DIRS = {'__pycache__'}


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


# ========================================
# Directory-based Import
# ========================================

def import_from_directory(
    directory: str | Path,
    base_package: str,
    excluded_dirs: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> List[DiscoveryFailure]:
    """ディレクトリから Python モジュールを再帰的にインポート
    
    ディレクトリ内の .py ファイルを走査し、モジュールとしてインポートします。
    ユーティリティディレクトリや __pycache__ などは自動的にスキップされます。
    
    Args:
        directory: インポート元ディレクトリパス
        base_package: ベースパッケージ名（例: 'myapp.routes'）
        excluded_dirs: 除外するディレクトリ名のセット（デフォルト: {'__pycache__'}）
        fail_on_error: True の場合、失敗時に DiscoveryError を発生
        
    Returns:
        失敗のリスト（空の場合はすべて成功）
        
    Raises:
        DiscoveryError: fail_on_error=True かつ失敗がある場合
        
    Example:
        # 基本的な使い方
        from pathlib import Path
        from repom._.discovery import import_from_directory
        
        failures = import_from_directory(
            directory=Path("src/myapp/routes"),
            base_package="myapp.routes"
        )
        
        # 除外ディレクトリを指定
        failures = import_from_directory(
            directory="src/myapp/models",
            base_package="myapp.models",
            excluded_dirs={'base', 'utils', '__pycache__'}
        )
        
        # エラー時に例外を発生
        failures = import_from_directory(
            directory="src/myapp/tasks",
            base_package="myapp.tasks",
            fail_on_error=True
        )
    """
    if excluded_dirs is None:
        excluded_dirs = DEFAULT_EXCLUDED_DIRS
    
    directory = Path(directory)
    failures = []
    
    # Collect all Python files to import
    py_files = []
    for py_file in directory.rglob('*.py'):
        # Skip __pycache__ directories
        if '__pycache__' in py_file.parts:
            continue
        
        # Skip files starting with underscore (like __init__.py)
        if py_file.stem.startswith('_'):
            continue
        
        # Skip excluded directories
        relative_path = py_file.relative_to(directory)
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
        except Exception as exc:
            failure = DiscoveryFailure(
                target=full_module_name,
                target_type="module",
                exception_type=type(exc).__name__,
                message=str(exc)
            )
            failures.append(failure)
    
    # Error handling
    if failures and fail_on_error:
        raise DiscoveryError(failures)
    
    return failures


# ========================================
# Package-based Import
# ========================================

def import_package_directory(
    package_name: str,
    excluded_dirs: Optional[Set[str]] = None,
    allowed_prefixes: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> List[DiscoveryFailure]:
    """パッケージ名からディレクトリを取得してインポート
    
    パッケージ名を指定すると、そのパッケージのディレクトリを自動検出し、
    配下のモジュールを再帰的にインポートします。
    
    Args:
        package_name: Python パッケージ名（例: 'myapp.models'）
        excluded_dirs: 除外するディレクトリ名のセット
        allowed_prefixes: 許可されたパッケージプレフィックス（セキュリティ）
        fail_on_error: エラー時に例外を発生させるか
        
    Returns:
        失敗のリスト（空の場合はすべて成功）
        
    Raises:
        ValueError: パッケージが許可リストにない、またはパッケージではない場合
        ImportError: パッケージが見つからない場合
        DiscoveryError: fail_on_error=True かつ失敗がある場合
        
    Example:
        from repom._.discovery import import_package_directory
        
        # 基本的な使い方
        failures = import_package_directory('myapp.models')
        
        # セキュリティ検証付き
        failures = import_package_directory(
            'myapp.routes',
            allowed_prefixes={'myapp.', 'shared.', 'repom.'}
        )
    """
    # セキュリティチェック
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
        
        # import_from_directory を使用してインポート
        return import_from_directory(
            directory=package_dir,
            base_package=package_name,
            excluded_dirs=excluded_dirs,
            fail_on_error=fail_on_error
        )
        
    except (ImportError, ValueError) as e:
        if fail_on_error:
            raise
        else:
            failure = DiscoveryFailure(
                target=package_name,
                target_type="package",
                exception_type=type(e).__name__,
                message=str(e)
            )
            return [failure]


def import_from_packages(
    package_names: str | List[str] | None,
    excluded_dirs: Optional[Set[str]] = None,
    allowed_prefixes: Optional[Set[str]] = None,
    fail_on_error: bool = False,
    post_import_hook: Optional[Callable[[], None]] = None
) -> List[DiscoveryFailure]:
    """複数のパッケージから一括インポート（フック付き）
    
    複数のパッケージを一括でインポートします。
    すべてのパッケージのインポート完了後に、オプションでコールバック関数を実行できます。
    
    Args:
        package_names: パッケージ名（文字列、リスト、カンマ区切り）
        excluded_dirs: 除外するディレクトリ名のセット
        allowed_prefixes: 許可されたパッケージプレフィックス（セキュリティ）
        fail_on_error: エラー時に例外を発生させるか
        post_import_hook: すべてのインポート完了後に呼ばれるコールバック
        
    Returns:
        失敗のリスト（空の場合はすべて成功）
        
    Raises:
        DiscoveryError: fail_on_error=True かつ失敗がある場合
        RuntimeError: post_import_hook の実行に失敗した場合
        
    Example:
        from repom._.discovery import import_from_packages
        
        # 基本的な使い方
        failures = import_from_packages([
            'myapp.routes',
            'myapp.tasks'
        ])
        
        # フック付き（SQLAlchemy モデル用）
        from sqlalchemy.orm import configure_mappers
        
        failures = import_from_packages(
            package_names=['myapp.models', 'shared.models'],
            post_import_hook=configure_mappers
        )
        
        # カンマ区切り文字列でも可
        failures = import_from_packages(
            'myapp.routes,myapp.api,myapp.tasks',
            allowed_prefixes={'myapp.'}
        )
    """
    # パスを正規化
    packages = normalize_paths(package_names)
    all_failures = []
    
    # すべてのパッケージをインポート
    for package_name in packages:
        failures = import_package_directory(
            package_name=package_name,
            excluded_dirs=excluded_dirs,
            allowed_prefixes=allowed_prefixes,
            fail_on_error=False  # 個別の失敗は集約
        )
        all_failures.extend(failures)
    
    # フック実行（すべてのインポート完了後）
    if post_import_hook:
        try:
            post_import_hook()
        except Exception as exc:
            error_msg = f"Post-import hook failed: {exc}"
            if fail_on_error:
                raise RuntimeError(error_msg) from exc
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(error_msg, exc_info=True)
    
    # エラーハンドリング
    if all_failures and fail_on_error:
        raise DiscoveryError(all_failures)
    
    return all_failures
