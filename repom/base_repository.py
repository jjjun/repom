"""
DEPRECATED: このファイルは後方互換性のためにのみ存在します。

新しいコードでは以下を使用してください:
    from repom import BaseRepository, FilterParams
    または
    from repom.repositories import BaseRepository, FilterParams

このインポートパスは将来のバージョン (v2.0+) で削除される予定です。
"""

import warnings

# 新しいパスから再エクスポート
from repom.repositories.base_repository import *  # noqa: F401, F403

# Deprecation warning
warnings.warn(
    "Importing from 'repom.base_repository' is deprecated. "
    "Use 'from repom import BaseRepository' or "
    "'from repom.repositories import BaseRepository' instead. "
    "This import path will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2
)
