"""repom - SQLAlchemy foundation package

このパッケージは、SQLAlchemy を使ったデータアクセス層の基盤を提供します。

公開名の一覧は `__all__` を参照してください。用途別の説明は
[README の公開 API 表](../README.md#公開-api)にまとめています。

推奨 import 例:
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
    gte_column,
    gt_column,
    lte_column,
    lt_column,
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
    'gte_column',
    'gt_column',
    'lte_column',
    'lt_column',
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
