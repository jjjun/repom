"""Core repository utilities shared by sync and async implementations

このモジュールは、同期版・非同期版リポジトリで共有されるロジックを提供します。
"""

from typing import Optional, List, Mapping, Any
from collections.abc import Iterable
from enum import Enum
from sqlalchemy import ColumnElement, UnaryExpression, asc, desc
from pydantic import BaseModel
from repom.repositories._order_by import normalize_order_by_value, VirtualColumnError


class FilterParams(BaseModel):
    """検索パラメータの基底クラス

    このクラスを継承してカスタムフィルタパラメータを定義し、
    find_by_params() で使用します。

    使用例:
        class MyFilterParams(FilterParams):
            name: Optional[str] = None
            tags: Optional[List[str]] = None
            _internal_id: Optional[int] = None  # プライベート（除外される）

        filters = MyFilterParams(name="foo")
        items = repo.find_by_params(filters)
    """


class MatchMode(str, Enum):
    """文字列フィールドの照合方法

    Attributes:
        EXACT: 完全一致（``==``）。field_to_column の既定値。
        PREFIX: 前方一致（``LIKE 'value%'``。ワイルドカードはエスケープされる）。
        CONTAINS: 部分一致（``LIKE '%value%'``。ワイルドカードはエスケープされる）。
    """

    EXACT = "exact"
    PREFIX = "prefix"
    CONTAINS = "contains"


# PREFIX / CONTAINS で LIKE に渡す文字列の既定の長さ上限。
# 交互ワイルドカードパターンによるバックトラッキング DoS を防ぐための上限であり、
# EXACT（== による比較）には適用されない。
DEFAULT_FILTER_STRING_MAX_LENGTH = 256


class MatchColumn:
    """field_to_column のマッピング値として使い、文字列の照合方法を明示するラッパー

    素のカラムを渡した場合は MatchMode.EXACT（完全一致）として扱われる。
    部分一致・前方一致が必要な場合は contains_column() / prefix_column() を使うこと。

    Args:
        column: マッピング先の SQLAlchemy カラム
        mode: 照合方法（既定は MatchMode.EXACT）
        max_length: PREFIX / CONTAINS で許可する文字列の最大長
    """

    __slots__ = ("column", "mode", "max_length")

    def __init__(
        self,
        column: Any,
        mode: MatchMode = MatchMode.EXACT,
        max_length: int = DEFAULT_FILTER_STRING_MAX_LENGTH,
    ):
        self.column = column
        self.mode = mode
        self.max_length = max_length


def contains_column(column: Any, max_length: int = DEFAULT_FILTER_STRING_MAX_LENGTH) -> MatchColumn:
    """field_to_column で部分一致（LIKE、ワイルドカードはエスケープ）を使うことを明示する"""
    return MatchColumn(column, MatchMode.CONTAINS, max_length)


def prefix_column(column: Any, max_length: int = DEFAULT_FILTER_STRING_MAX_LENGTH) -> MatchColumn:
    """field_to_column で前方一致（LIKE、ワイルドカードはエスケープ）を使うことを明示する"""
    return MatchColumn(column, MatchMode.PREFIX, max_length)


def has_soft_delete(model_class) -> bool:
    """モデルが SoftDeletableMixin を持つか確認

    Args:
        model_class: SQLAlchemy モデルクラス

    Returns:
        bool: deleted_at カラムが存在する場合 True
    """
    return hasattr(model_class, 'deleted_at')


def _value_to_filter(
    column: Any,
    value: Any,
    mode: MatchMode = MatchMode.EXACT,
    max_length: int = DEFAULT_FILTER_STRING_MAX_LENGTH,
):
    """Map a single value to a SQLAlchemy filter expression.

    - Iterable values (except str/bytes) use ``column.in_(...)``
    - str values use ``==`` (exact match) unless ``mode`` requests PREFIX or
      CONTAINS, in which case an escaped LIKE is used (``autoescape=True``)
      so literal ``%``/``_`` characters in the value are treated literally
      rather than as wildcards. Values longer than ``max_length`` are
      rejected before reaching LIKE to guard against backtracking-heavy
      wildcard patterns.
    - Other values fall back to ``==``
    """
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return column.in_(list(value))

    if isinstance(value, str) and mode is not MatchMode.EXACT and hasattr(column, 'contains'):
        if len(value) > max_length:
            raise ValueError(
                f"Filter value exceeds the maximum length of {max_length} characters allowed for LIKE matching."
            )
        if mode is MatchMode.PREFIX:
            return column.startswith(value, autoescape=True)
        return column.contains(value, autoescape=True)

    return column == value


def build_filters_from_mapping(params: FilterParams, field_to_column: Mapping[str, Any]) -> list:
    """Convert FilterParams into SQLAlchemy filters using a field->column mapping.

    Args:
        params: Filter parameters instance (None values are ignored)
        field_to_column: Mapping of FilterParams field names to SQLAlchemy
            columns/expressions, or to a MatchColumn (see contains_column() /
            prefix_column()) when a str field needs LIKE matching instead of
            the default exact match.

    Returns:
        list: SQLAlchemy filter expressions generated from non-None fields
    """
    filters = []

    for field_name, mapped in field_to_column.items():
        if mapped is None:
            continue

        value = getattr(params, field_name, None)
        if value is None:
            continue

        if isinstance(mapped, MatchColumn):
            filters.append(_value_to_filter(mapped.column, value, mapped.mode, mapped.max_length))
        else:
            filters.append(_value_to_filter(mapped, value))

    return filters


def parse_order_by(
    model_class,
    order_by_str: str,
    allowed_order_columns: List[str],
    virtual_order_columns: Optional[List[str]] = None,
):
    """Parse order_by string and return SQLAlchemy order expression.

    Format: "column_name:direction" (e.g., "created_at:desc", "id:asc")

    Column names must be in the allowed_order_columns whitelist (security measure).
    Subclasses can extend the whitelist by overriding allowed_order_columns:

    Example:
        class MyRepository(BaseRepository):
            allowed_order_columns = BaseRepository.allowed_order_columns + ['custom_field']

    Args:
        model_class: The SQLAlchemy model class
        order_by_str: Order specification string (e.g., "created_at:desc")
        allowed_order_columns: List of column names allowed for sorting

    Returns:
        SQLAlchemy column expression with asc() or desc()

    Raises:
        ValueError: If format is invalid, column is not in whitelist, direction is invalid,
            or column doesn't exist
    """
    column_name, direction = normalize_order_by_value(order_by_str)

    # Validate column against whitelist
    if column_name not in allowed_order_columns:
        raise ValueError(f"Column '{column_name}' is not allowed for sorting")

    # Validate direction
    if direction not in ['asc', 'desc']:
        raise ValueError(f"Direction must be 'asc' or 'desc', got '{direction}'")

    # Virtual columns are allowed for API exposure but must be handled by callers.
    if virtual_order_columns and column_name in set(virtual_order_columns):
        raise VirtualColumnError(column_name, direction)

    # Validate column exists on model
    if not hasattr(model_class, column_name):
        raise ValueError(f"Column '{column_name}' does not exist on model")

    column = getattr(model_class, column_name)

    return desc(column) if direction == 'desc' else asc(column)


def set_find_option(
    query,
    model,
    allowed_order_columns: List[str],
    virtual_order_columns: Optional[List[str]] = None,
    default_options: Optional[List] = None,
    default_order_by=None,
    max_limit: Optional[int] = None,
    **kwargs
):
    """
    クエリにオプションを設定するメソッド。

    このメソッドは、クエリに対して offset、limit、order_by、および options を設定します。
    デフォルトでは、order_by はモデルの id フィールドの昇順に設定されます。
    リポジトリの default_order_by（クラス/インスタンス属性）を指定すると、
    order_by 引数が渡されていない場合にその設定が優先されます。

    desc(降順): 値が大きいものから小さいもの順に並べる
    asc(昇順): 値が小さいものから大きいもの順に並べる

    Args:
        query: SQLAlchemy のクエリオブジェクト。
        model: SQLAlchemy モデルクラス
        allowed_order_columns: ソート可能なカラム名のリスト
        default_options: デフォルトの eager loading options（リポジトリの default_options）
            クラス属性が優先され、options=None のときのみ適用されます。
        default_order_by: デフォルトの order_by 設定（リポジトリの default_order_by）
            クラス属性が優先され、order_by が未指定の場合に適用されます。
        max_limit: 許可する limit の最大値（リポジトリの max_limit クラス属性）。
            limit がこれを超えると ValueError を送出します。None の場合は上限
            チェックを行いません。
        **kwargs: 任意のキーワード引数。以下の引数をサポートします。
            - offset (int): 取得するデータの開始位置。0 以上の整数。未指定の場合は
              offset を適用しません（先頭から取得）。
            - limit (int): 取得するデータの件数。0 以上 max_limit 以下の整数。
              bool は真偽値であり件数として無効なため拒否します。未指定の場合は
              上限なしで全件を取得します（find() は limit 省略時に
              RuntimeWarning を送出します。呼び出し側が明示的に制限してください）。
            - order_by (Callable | str): 結果を並べ替えるための呼び出し可能オブジェクト。デフォルトはモデルの id フィールドの昇順。
            - options (list | Load): SQLAlchemy の load options (joinedload, selectinload など)。
              None の場合は default_options を使用。空リスト [] を渡すと eager loading なし。

    Returns:
        クエリオブジェクトにオプションを設定したものを返します。

    使用例:
        # Eager loading を使用して N+1 問題を解決
        from sqlalchemy.orm import joinedload, selectinload

        results = repo.find(
            filters=[Model.status == 'active'],
            options=[joinedload(Model.user)]  # 関連モデルを eager load
        )

        # 複数の options を指定
        results = repo.find(
            options=[
                joinedload(Model.user),
                selectinload(Model.tags)
            ]
        )

        # default_options をスキップ（eager loading なし）
        results = repo.find(options=[])  # 空リストを明示的に渡す
        apply_order_by (bool): Whether to apply the resolved order_by option.

    """
    offset = kwargs.get('offset', None)
    limit = kwargs.get('limit', None)
    options = kwargs.get('options', None)
    apply_order_by = kwargs.get('apply_order_by', True)
    # order_by の処理: None または空文字の場合は default_order_by を適用
    order_by = kwargs.get('order_by')
    if order_by is None or order_by == "":
        order_by = default_order_by

    # options の処理: None の場合のみ default_options を使用
    if options is None and default_options:
        options = default_options

    if options is not None:
        if isinstance(options, list):
            for opt in options:
                query = query.options(opt)
        else:
            query = query.options(options)

    # order_by の型に応じて処理を分岐
    if isinstance(order_by, str):
        # 文字列の場合は変換
        order_by = parse_order_by(
            model,
            order_by,
            allowed_order_columns,
            virtual_order_columns,
        )
    elif isinstance(order_by, (UnaryExpression, ColumnElement)):
        # SQLAlchemy のカラムオブジェクトの場合はそのまま使用
        pass
    elif order_by is None:
        # 指定がない場合はデフォルト（id の昇順）。id カラムを持たないモデル
        # （use_id=False）では、フォールバック先が無いため order_by は None のまま
        # とし、ORDER BY を付与しない。
        if hasattr(model, 'id'):
            order_by = model.id.asc()

    if offset is not None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("offset must be an integer")
        if offset < 0:
            raise ValueError("offset must not be negative")
        query = query.offset(offset)
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must not be negative")
        if max_limit is not None and limit > max_limit:
            raise ValueError(f"limit must not exceed max_limit ({max_limit})")
        query = query.limit(limit)
    if apply_order_by and order_by is not None:
        query = query.order_by(order_by)

    return query
