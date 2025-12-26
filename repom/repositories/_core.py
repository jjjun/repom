"""Core repository utilities shared by sync and async implementations

このモジュールは、同期版・非同期版リポジトリで共有されるロジックを提供します。
"""

from typing import Optional, List
from sqlalchemy import ColumnElement, UnaryExpression, asc, desc
from pydantic import BaseModel
import inspect
import logging

logger = logging.getLogger(__name__)


class FilterParams(BaseModel):
    """FastAPI クエリパラメータとして使用できるフィルタパラメータ基底クラス

    このクラスを継承してカスタムフィルタパラメータを定義し、
    as_query_depends() を使用して FastAPI の Depends() と組み合わせます。

    使用例:
        class MyFilterParams(FilterParams):
            name: Optional[str] = None
            tags: Optional[List[str]] = None
            _internal_id: Optional[int] = None  # プライベート（除外される）

        @app.get("/items")
        async def get_items(filters: MyFilterParams = Depends(MyFilterParams.as_query_depends())):
            # filters を使用して検索
            items = repo.find_by_params(filters)
            return items
    """
    # セキュリティ: クエリパラメータとして公開しないフィールド
    _excluded_from_query: set = set()

    @classmethod
    def as_query_depends(cls):
        """FilterParams を FastAPI の Query パラメータとして使用できる depends 関数に変換

        List[str] などの配列型も正しくクエリパラメータとして扱われます。

        セキュリティ:
        - _excluded_from_query に指定されたフィールドは除外されます
        - プライベートフィールド (_で始まる) は自動的に除外されます

        使用例:
            class MyFilterParams(FilterParams):
                name: Optional[str] = None
                tags: Optional[List[str]] = None
                _internal_id: Optional[int] = None  # 自動的に除外

            # または明示的に除外
            class SecureFilterParams(FilterParams):
                _excluded_from_query = {"sensitive_field"}
                public_field: Optional[str] = None
                sensitive_field: Optional[str] = None  # 除外される

            # ルートで使用
            filter_params: MyFilterParams = Depends(MyFilterParams.as_query_depends())

        Returns:
            Callable: FastAPI の Depends() で使用できる関数
        """
        from fastapi import Query

        # Pydantic v2 のフィールド情報を取得
        fields = cls.model_fields

        # 除外するフィールドのセット（クラス変数から取得、存在しない場合は空セット）
        excluded = set()
        if hasattr(cls, '_excluded_from_query'):
            excluded_value = getattr(cls, '_excluded_from_query')
            # ModelPrivateAttr オブジェクトの場合はデフォルト値を取得
            if hasattr(excluded_value, 'default'):
                excluded = excluded_value.default if excluded_value.default is not None else set()
            elif isinstance(excluded_value, set):
                excluded = excluded_value

        # 動的に関数のシグネチャを構築
        params = []
        annotations = {}

        for field_name, field_info in fields.items():
            # セキュリティ: プライベートフィールドと除外リストをスキップ
            if field_name.startswith('_') or field_name in excluded:
                continue

            # 型アノテーションを取得
            field_type = field_info.annotation

            # デフォルト値を Query() でラップ
            default_value = field_info.default if field_info.default is not None else None

            # description を取得（あれば）
            description = field_info.description or f"Filter by {field_name}"

            # Query() パラメータを作成
            query_param = Query(default_value, description=description)

            params.append((field_name, field_type, query_param))
            annotations[field_name] = field_type

        # 動的に depends 関数を生成
        def query_depends(**kwargs):
            return cls(**kwargs)

        # 関数のシグネチャを動的に設定
        sig_params = [
            inspect.Parameter(
                name=name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation
            )
            for name, annotation, default in params
        ]

        query_depends.__signature__ = inspect.Signature(
            parameters=sig_params,
            return_annotation=cls
        )
        query_depends.__annotations__ = annotations

        return query_depends


def has_soft_delete(model_class) -> bool:
    """モデルが SoftDeletableMixin を持つか確認

    Args:
        model_class: SQLAlchemy モデルクラス

    Returns:
        bool: deleted_at カラムが存在する場合 True
    """
    return hasattr(model_class, 'deleted_at')


def parse_order_by(model_class, order_by_str: str, allowed_order_columns: List[str]):
    """Parse order_by string and return SQLAlchemy order expression.

    Format: "column_name:direction" (e.g., "created_at:desc", "id:asc")
    Direction defaults to "asc" if not specified.

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
        ValueError: If column is not in whitelist, direction is invalid, or column doesn't exist
    """
    if ':' not in order_by_str:
        column_name = order_by_str.strip()
        direction = 'asc'
    else:
        parts = order_by_str.split(':', 1)
        column_name = parts[0].strip()
        direction = parts[1].strip().lower()

    # Validate column against whitelist
    if column_name not in allowed_order_columns:
        raise ValueError(f"Column '{column_name}' is not allowed for sorting")

    # Validate direction
    if direction not in ['asc', 'desc']:
        raise ValueError(f"Direction must be 'asc' or 'desc', got '{direction}'")

    # Validate column exists on model
    if not hasattr(model_class, column_name):
        raise ValueError(f"Column '{column_name}' does not exist on model")

    column = getattr(model_class, column_name)

    return desc(column) if direction == 'desc' else asc(column)


def set_find_option(query, model, allowed_order_columns: List[str], **kwargs):
    """
    クエリにオプションを設定するメソッド。

    このメソッドは、クエリに対して offset、limit、order_by、および options を設定します。
    デフォルトでは、order_by はモデルの id フィールドの昇順に設定されます。

    desc(降順): 値が大きいものから小さいもの順に並べる
    asc(昇順): 値が小さいものから大きいもの順に並べる

    Args:
        query: SQLAlchemy のクエリオブジェクト。
        model: SQLAlchemy モデルクラス
        allowed_order_columns: ソート可能なカラム名のリスト
        **kwargs: 任意のキーワード引数。以下の引数をサポートします。
            - offset (int): 取得するデータの開始位置。デフォルトは 0。
            - limit (int): 取得するデータの件数。デフォルトは 10。
            - order_by (Callable | str): 結果を並べ替えるための呼び出し可能オブジェクト。デフォルトはモデルの id フィールドの昇順。
            - options (list | Load): SQLAlchemy の load options (joinedload, selectinload など)。

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
    """
    offset = kwargs.get('offset', None)
    limit = kwargs.get('limit', None)
    options = kwargs.get('options', None)
    # 特に指定しない場合、デフォルトで昇順になるんだけど、此処では明示的に指定してる
    # order_by が指定されていない場合はデフォルト
    order_by = model.id.asc()

    # options の処理
    if options is not None:
        if isinstance(options, list):
            for opt in options:
                query = query.options(opt)
        else:
            query = query.options(options)

    # order_by の型に応じて処理を分岐
    if 'order_by' in kwargs:
        if isinstance(kwargs['order_by'], str):
            # 文字列の場合は変換
            order_by = parse_order_by(model, kwargs['order_by'], allowed_order_columns)
        elif isinstance(kwargs['order_by'], (UnaryExpression, ColumnElement)):
            # SQLAlchemy のカラムオブジェクトの場合はそのまま使用
            order_by = kwargs['order_by']

    if offset is not None:
        if not isinstance(offset, int):
            raise TypeError("offset must be an integer")
        query = query.offset(offset)
    if limit is not None:
        if not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        query = query.limit(limit)
    if order_by is not None:
        query = query.order_by(order_by)

    return query
