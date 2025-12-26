"""
DEPRECATED: このファイルは後方互換性のためにのみ存在します。

新しいコードでは以下を使用してください:
    from repom import AsyncBaseRepository
    または
    from repom.repositories import AsyncBaseRepository

このインポートパスは将来のバージョン (v2.0+) で削除される予定です。
"""

import warnings

# 新しいパスから再エクスポート
from repom.repositories.async_base_repository import *  # noqa: F401, F403

# Deprecation warning
warnings.warn(
    "Importing from 'repom.async_base_repository' is deprecated. "
    "Use 'from repom import AsyncBaseRepository' or "
    "'from repom.repositories import AsyncBaseRepository' instead. "
    "This import path will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2
)
