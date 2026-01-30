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

Example:
    >>> from repom._.discovery import import_packages
    >>> failures = import_packages("myapp.routes,myapp.tasks")
    >>> if failures:
    ...     print(f"Failed: {[f.target for f in failures]}")
"""

import importlib
from dataclasses import dataclass
from typing import Optional, Set, List, Literal, Sequence


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
