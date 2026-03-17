"""Repository package

このパッケージは、SQLAlchemy を使ったデータアクセス層を提供します。

Available Classes:
- BaseRepository: 同期版リポジトリ
- AsyncBaseRepository: 非同期版リポジトリ
- QueryBuilderMixin: 同期/非同期共通のクエリ構築ミックスイン
- FilterParams: 検索パラメータの基底クラス
"""

from repom.repositories._core import FilterParams
from repom.repositories._order_by import (
    build_order_by_query_depends,
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
    'build_order_by_query_depends',
    'get_order_by_columns',
    'get_order_by_default_value',
    'get_order_by_values',
    'VirtualColumnError',
]
