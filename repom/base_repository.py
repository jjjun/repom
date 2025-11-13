from typing import Any, Callable, Type, TypeVar, Generic, Optional, List, Dict, Union
from sqlalchemy import ColumnElement, UnaryExpression, and_, select, asc, desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from repom.db import db_session
import inspect

T = TypeVar('T')


class FilterParams(BaseModel):
    # セキュリティ: クエリパラメータとして公開しないフィールド
    _excluded_from_query: set = set()

    @classmethod
    def as_query_depends(cls):
        """
        FilterParams を FastAPI の Query パラメータとして使用できる depends 関数に変換

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


class BaseRepository(Generic[T]):
    # Default allowed columns for order_by operations (can be extended by subclasses)
    allowed_order_columns = [
        'id', 'title', 'created_at', 'updated_at',
        'started_at', 'finished_at', 'executed_at'
    ]

    def __init__(self, model: Type[T], session: Session = db_session):
        """
        BaseRepositoryの初期化

        Args:
            model (Type[T]): モデルクラス
            session (Session, optional): データベースセッション. Defaults to db_session.
        """
        self.model = model
        self.session = session

    def get_by(
        self,
        column_name: str,
        value: Any,
        *extra_filters: ColumnElement,
        single: bool = False,
    ) -> Union[List[T], Optional[T]]:
        """Retrieve records by the specified column name and value.

        Additional SQLAlchemy filter expressions can be supplied via ``extra_filters``
        to further narrow down the query. By default all matching records are
        returned; when ``single`` is ``True`` only the first match is returned.
        """
        if not hasattr(self.model, column_name):
            raise AttributeError(f"Column '{column_name}' does not exist on {self.model.__name__}")

        column = getattr(self.model, column_name)
        filters = [column == value, *extra_filters]
        if single:
            return self.find_one(filters=filters)
        return self.find(filters=filters)

    def get_by_id(self, id: int) -> Optional[T]:
        """
        指定されたIDのインスタンスを取得

        Args:
            id (int): インスタンスのID

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone
        """
        return self.get_by('id', id, single=True)

    def get_all(self) -> List[T]:
        """
        全てのインスタンスを取得

        Returns:
            List[T]: 全てのインスタンスのリスト
        """
        return self.session.query(self.model).all()

    def save(self, instance: T) -> T:
        """
        インスタンスを保存

        Args:
            instance (T): 保存するインスタンス
        Returns:
            T: 保存したインスタンス
        """
        try:
            self.session.add(instance)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return instance

    def dict_save(self, data: Dict) -> T:
        """
        dict型のデータをモデルインスタンスにして保存

        Args:
            data (Dict): 保存するデータ
        Returns:
            T: 保存したインスタンス
        """
        instance = self.model(**data)
        return self.save(instance)

    def saves(self, instances: List[T]) -> None:
        """
        Listの中に入ったインスタンスを保存

        Args:
            instances (List[T]): 保存するインスタンスのリスト
        """
        try:
            self.session.add_all(instances)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def dict_saves(self, data_list: List[Dict]) -> None:
        """
        Listの中に入ったdict型のデータをモデルインスタンスにして保存

        Args:
            data_list (List[Dict]): 保存するデータのリスト
        """
        instances = [self.model(**data) for data in data_list]
        self.saves(instances)

    def remove(self, instance: T) -> None:
        """
        インスタンスを削除

        Args:
            instance (T): 削除するインスタンス
        """
        try:
            self.session.delete(instance)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def set_find_option(self, query, **kwargs):
        """
        クエリにオプションを設定するメソッド。

        このメソッドは、クエリに対して offset、limit、および order_by オプションを設定します。
        デフォルトでは、order_by はモデルの id フィールドの降順に設定されます。

        desc(降順): 値が大きいものから小さいもの順に並べる
        asc(昇順): 値が小さいものから大きいもの順に並べる

        Args:
            query: SQLAlchemy のクエリオブジェクト。
            **kwargs: 任意のキーワード引数。以下の引数をサポートします。
                - offset (int): 取得するデータの開始位置。デフォルトは 0。
                - limit (int): 取得するデータの件数。デフォルトは 10。
                - order_by (Callable): 結果を並べ替えるための呼び出し可能オブジェクト。デフォルトはモデルの id フィールドの降順。

        Returns:
            クエリオブジェクトにオプションを設定したものを返します。
        """
        offset = kwargs.get('offset', None)
        limit = kwargs.get('limit', None)
        # 特に指定しない場合、デフォルトで昇順になるんだけど、此処では明示的に指定してる
        # order_by が指定されていない場合はデフォルト
        order_by = self.model.id.asc()

        # order_by の型に応じて処理を分岐
        if 'order_by' in kwargs:
            if isinstance(kwargs['order_by'], str):
                # 文字列の場合は変換
                order_by = self.parse_order_by(self.model, kwargs['order_by'])
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

    def parse_order_by(self, model_class, order_by_str: str):
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
        if column_name not in self.allowed_order_columns:
            raise ValueError(f"Column '{column_name}' is not allowed for sorting")

        # Validate direction
        if direction not in ['asc', 'desc']:
            raise ValueError(f"Direction must be 'asc' or 'desc', got '{direction}'")

        # Validate column exists on model
        if not hasattr(model_class, column_name):
            raise ValueError(f"Column '{column_name}' does not exist on model")

        column = getattr(model_class, column_name)

        return desc(column) if direction == 'desc' else asc(column)

    def _build_filters(self, params: Optional[FilterParams]) -> list:
        # デフォルトは何もフィルタしない
        return []

    def find(self, filters: Optional[List[Callable]] = None, **kwargs) -> List[T]:
        """
        共通の find メソッド。特に指定が無ければ全件を取得する。
        取得量を絞りたい場合は、offset と limit を指定する。

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト。
            **kwargs: 任意のキーワード引数。

        Returns:
            List[T]: モデルのリスト。
        """
        query = select(self.model)
        if filters:
            query = query.where(and_(*filters))
        query = self.set_find_option(query, **kwargs)
        return self.session.execute(query).scalars().all()

    def find_one(self, filters: list) -> Optional[T]:
        """
        Retrieve a single record based on the provided filters (SQLAlchemy expressions list).

        Args:
            filters (list): フィルタ条件のリスト。

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone
        """
        query = select(self.model).filter(*filters).limit(1)
        result = self.session.execute(query).scalars().first()
        return result

    def count(self, filters: Optional[List[Callable]] = None) -> int:
        """
        指定したフィルタ条件に一致するレコード数を返す

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト。

        Returns:
            int: 一致するレコード数
        """
        query = self.session.query(self.model)
        if filters:
            query = query.filter(and_(*filters))
        return query.count()

    def count_by_params(self, params: Optional[FilterParams] = None) -> int:
        filters = self._build_filters(params) if params else []
        return self.count(filters=filters)
