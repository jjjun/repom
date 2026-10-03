"""
リポジトリのクエリ構築機能ミックスイン.

同期・非同期の両方のベースリポジトリで共有される
クエリ構築・フィルタリング関連のメソッドを提供します。
"""

from collections.abc import Sequence
from typing import Any, Generic, Mapping, Optional, TypeVar

from sqlalchemy import select

from repom.repositories._core import (
    FilterParams,
    parse_order_by,
    set_find_option,
    build_filters_from_mapping,
)

T = TypeVar('T')


class QueryBuilderMixin(Generic[T]):
    """クエリ構築関連の共通機能（同期/非同期で共通）.

    BaseRepository と AsyncBaseRepository で共有される
    クエリ構築・フィルタリング関連のメソッドを提供します。

    Attributes:
        allowed_order_columns: ソート可能なカラムのホワイトリスト（サブクラスで拡張可能）
        default_options: eager loading のデフォルト設定（クラス属性としても設定可能）
        default_order_by: order_by のデフォルト設定（クラス属性としても設定可能）
        max_limit: limit に許可する最大値（クラス属性としても設定可能）。
            None にすると上限チェックを無効化できます。
    """

    # Default allowed columns for order_by operations (can be extended by subclasses)
    allowed_order_columns = [
        'id', 'title', 'created_at', 'updated_at',
        'started_at', 'finished_at', 'executed_at'
    ]
    virtual_order_columns: list[str] = []
    # デフォルトの eager loading options
    default_options: Sequence[Any] = ()
    default_order_by = None
    # 明示された root row limit の上限（サブクラスで上書き可能）。None で上限チェックを無効化。
    # offset、IN リスト、relationship 展開、クエリコストは制限しない。
    max_limit: Optional[int] = 1000
    field_to_column: Optional[Mapping[str, Any]] = None

    def _base_select(self):
        """Build the base SELECT for this repository.

        Override to customise statement construction, such as execution
        options or hints. Standard repository query paths use this hook, but it
        does not cover every model load: get_or_create() builds direct SELECT
        statements, internal-session save paths call session.refresh(), and
        remove() uses merge(). Do not apply filtering here; filters are the
        caller's contract.
        """
        return select(self.model)

    def set_find_option(self, query, **kwargs):
        """クエリにオプションを設定するメソッド（_core.set_find_option を呼び出し）"""
        return set_find_option(
            query,
            self.model,
            self.allowed_order_columns,
            self.virtual_order_columns,
            self.default_options,
            self.default_order_by,
            self.max_limit,
            **kwargs
        )

    def parse_order_by(self, model_class, order_by_str: str):
        """Parse order_by string（_core.parse_order_by を呼び出し）"""
        return parse_order_by(
            model_class,
            order_by_str,
            self.allowed_order_columns,
            self.virtual_order_columns,
        )

    def _uses_default_filter_builder(self) -> bool:
        # Overrides may handle additional fields after delegating mapped fields to super().
        return type(self)._build_filters is QueryBuilderMixin._build_filters

    def _build_filters(self, params: Optional[FilterParams]) -> list:
        """FilterParams からフィルタ条件を構築

        デフォルト実装では、パラメータが指定されない場合や、すべてのフィールドが
        None の場合は空リストを返します。
        """
        if params is None:
            return []

        if all(value is None for value in params.model_dump().values()):
            return []

        mapping = self.field_to_column or {}
        unhandled_fields = set(params.model_dump(exclude_none=True)) - {
            field_name for field_name, column in mapping.items() if column is not None
        }
        if unhandled_fields and self._uses_default_filter_builder():
            fields = ", ".join(sorted(unhandled_fields))
            raise ValueError(
                f"{type(self).__name__} has unmapped FilterParams fields: {fields}. "
                "Add a field_to_column mapping or override _build_filters()."
            )

        filters = []

        if mapping:
            filters.extend(build_filters_from_mapping(params, mapping))

        return filters
