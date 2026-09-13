"""repom - SQLAlchemy foundation package

このパッケージは、SQLAlchemy を使ったデータアクセス層の基盤を提供します。

Available Classes:
- BaseModel: SQLAlchemy モデルの基底クラス
- BaseRepository: 同期版リポジトリ
- AsyncBaseRepository: 非同期版リポジトリ
- FilterParams: 検索パラメータの基底クラス
- SoftDeletableMixin: 論理削除機能を追加する Mixin

Recommended Import Style (推奨):
    from repom import BaseRepository, AsyncBaseRepository
    from repom import FilterParams, SoftDeletableMixin
    from repom import BaseModel
"""

# Core models
from repom.models import BaseModel
from repom.exceptions import NulByteError

# Repositories
from repom.repositories import (
    BaseRepository,
    AsyncBaseRepository,
    FilterParams,
    MatchMode,
    MatchColumn,
    contains_column,
    prefix_column,
    get_order_by_columns,
    get_order_by_default_value,
    get_order_by_values,
    VirtualColumnError,
)

# Mixins
from repom.mixins import SoftDeletableMixin

# Query Analysis
from repom.diagnostics.query_analyzer import QueryAnalyzer

# Logging utilities
from repom.logging import make_timed_rotating_handler, DateNamedDailyFileHandler

__all__ = [
    # Models
    'BaseModel',
    'NulByteError',
    # Repositories
    'BaseRepository',
    'AsyncBaseRepository',
    'FilterParams',
    'MatchMode',
    'MatchColumn',
    'contains_column',
    'prefix_column',
    'get_order_by_columns',
    'get_order_by_default_value',
    'get_order_by_values',
    'VirtualColumnError',
    # Mixins
    'SoftDeletableMixin',
    # Query Analysis
    'QueryAnalyzer',
    # Logging utilities
    'make_timed_rotating_handler',
    'DateNamedDailyFileHandler',
]
