"""
リポジトリのクエリ構築機能ミックスイン.

同期・非同期の両方のベースリポジトリで共有される
クエリ構築・フィルタリング関連のメソッドを提供します。
"""

from typing import Generic, Optional, TypeVar

from repom.repositories._core import FilterParams, parse_order_by, set_find_option

T = TypeVar('T')


class QueryBuilderMixin(Generic[T]):
    """クエリ構築関連の共通機能（同期/非同期で共通）.

    BaseRepository と AsyncBaseRepository で共有される
    クエリ構築・フィルタリング関連のメソッドを提供します。

    Attributes:
        allowed_order_columns: ソート可能なカラムのホワイトリスト（サブクラスで拡張可能）
    """

    # Default allowed columns for order_by operations (can be extended by subclasses)
    allowed_order_columns = [
        'id', 'title', 'created_at', 'updated_at',
        'started_at', 'finished_at', 'executed_at'
    ]

    def set_find_option(self, query, **kwargs):
        """クエリにオプションを設定するメソッド（_core.set_find_option を呼び出し）"""
        default_options = getattr(self, 'default_options', [])
        return set_find_option(query, self.model, self.allowed_order_columns, default_options, **kwargs)

    def parse_order_by(self, model_class, order_by_str: str):
        """Parse order_by string（_core.parse_order_by を呼び出し）"""
        return parse_order_by(model_class, order_by_str, self.allowed_order_columns)

    def _build_filters(self, params: Optional[FilterParams]) -> list:
        """FilterParams からフィルタ条件を構築

        デフォルト実装では、パラメータが指定されない場合や、すべてのフィールドが
        None の場合は空リストを返します。
        """
        if params is None:
            return []

        if all(value is None for value in params.model_dump().values()):
            return []

        return []
