"""Repository package

このパッケージは、SQLAlchemy を使ったデータアクセス層を提供します。

Available Classes:
- BaseRepository: 同期版リポジトリ
- AsyncBaseRepository: 非同期版リポジトリ
- QueryBuilderMixin: 同期/非同期共通のクエリ構築ミックスイン
- FilterParams: 検索パラメータの基底クラス
- MatchMode / MatchColumn / contains_column / prefix_column: field_to_column
  で文字列の照合方法（完全一致・前方一致・部分一致）を明示するためのヘルパー
"""

from repom.repositories._core import (
    FilterParams,
    MatchMode,
    MatchColumn,
    contains_column,
    prefix_column,
)
from repom.repositories._introspection import (
    create_repository_instance,
    get_model_from_repository_class,
)
from repom.repositories._order_by import (
    get_order_by_columns,
    get_order_by_default_value,
    get_order_by_values,
    VirtualColumnError,
)
from repom.repositories._query_builder import QueryBuilderMixin
from repom.repositories.base_repository import BaseRepository
from repom.repositories.async_base_repository import AsyncBaseRepository

__all__ = [
    'BaseRepository',
    'AsyncBaseRepository',
    'QueryBuilderMixin',
    'FilterParams',
    'MatchMode',
    'MatchColumn',
    'contains_column',
    'prefix_column',
    'get_order_by_columns',
    'get_order_by_default_value',
    'get_order_by_values',
    'VirtualColumnError',
    'create_repository_instance',
    'get_model_from_repository_class',
]
