from typing import Any, Callable, Type, TypeVar, Generic, Optional, List, Dict, Union
from datetime import datetime
from sqlalchemy import ColumnElement, UnaryExpression, and_, select, asc, desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
from pydantic.fields import FieldInfo
import inspect
import logging

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


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

    def __init__(self, model: Type[T], session: Optional[Session] = None):
        """
        BaseRepositoryの初期化

        Args:
            model (Type[T]): モデルクラス
            session (Session, optional): データベースセッション. Defaults to None (get_db_session() を使用).
        """
        self.model = model
        self.session = session

    def _has_soft_delete(self) -> bool:
        """モデルが SoftDeletableMixin を持つか確認

        Returns:
            bool: deleted_at カラムが存在する場合 True
        """
        return hasattr(self.model, 'deleted_at')

    def get_by(
        self,
        column_name: str,
        value: Any,
        *extra_filters: ColumnElement,
        single: bool = False,
        options: Optional[List] = None
    ) -> Union[List[T], Optional[T]]:
        """Retrieve records by the specified column name and value.

        Additional SQLAlchemy filter expressions can be supplied via ``extra_filters``
        to further narrow down the query. By default all matching records are
        returned; when ``single`` is ``True`` only the first match is returned.

        Args:
            column_name: 検索するカラム名
            value: 検索する値
            extra_filters: 追加のフィルタ条件
            single: True の場合は最初の1件のみ返す
            options: SQLAlchemy クエリオプション（eager loading等）

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> # 単一レコード取得（relationship も eager load）
            >>> item = repo.get_by(
            ...     'email', 'user@example.com',
            ...     single=True,
            ...     options=[selectinload(User.profile)]
            ... )
        """
        if not hasattr(self.model, column_name):
            raise AttributeError(f"Column '{column_name}' does not exist on {self.model.__name__}")

        column = getattr(self.model, column_name)
        filters = [column == value, *extra_filters]
        if single:
            return self.find_one(filters=filters, options=options)
        return self.find(filters=filters, options=options)

    def get_by_id(self, id: int, include_deleted: bool = False, options: Optional[List] = None) -> Optional[T]:
        """
        指定されたIDのインスタンスを取得

        Args:
            id (int): インスタンスのID
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            options (Optional[List]): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone

        Example:
            >>> # シンプルな取得（従来通り）
            >>> item = repo.get_by_id(123)
            >>> 
            >>> # relationship も一緒に取得（N+1問題を回避）
            >>> from sqlalchemy.orm import selectinload
            >>> item = repo.get_by_id(123, options=[
            ...     selectinload(Model.tags),
            ...     selectinload(Model.reviews)
            ... ])
        """
        extra_filters = []
        if self._has_soft_delete() and not include_deleted:
            extra_filters.append(self.model.deleted_at.is_(None))

        return self.get_by('id', id, *extra_filters, single=True, options=options)

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

        Note:
            同期版では refresh() は不要です。
            理由: SQLAlchemy の同期セッションでは expire_on_commit=True (デフォルト) により、
                  commit() 後に属性アクセス時、自動的にデータベースから再読み込みが発生します。
                  そのため、AutoDateTime などのデフォルト値も正しく取得できます。

            非同期版（AsyncBaseRepository.save）では refresh() が必須です。
        """
        try:
            self.session.add(instance)
            self.session.commit()
            # 同期版では refresh() 不要（expire_on_commit により自動ロードされる）
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

        Note:
            同期版では refresh() は不要です（属性アクセス時に自動ロード）。
            非同期版（AsyncBaseRepository.saves）では各インスタンスの refresh() が必須です。
        """
        try:
            self.session.add_all(instances)
            self.session.commit()
            # 同期版では refresh() 不要（expire_on_commit により自動ロードされる）
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

        このメソッドは、クエリに対して offset、limit、order_by、および options を設定します。
        デフォルトでは、order_by はモデルの id フィールドの降順に設定されます。

        desc(降順): 値が大きいものから小さいもの順に並べる
        asc(昇順): 値が小さいものから大きいもの順に並べる

        Args:
            query: SQLAlchemy のクエリオブジェクト。
            **kwargs: 任意のキーワード引数。以下の引数をサポートします。
                - offset (int): 取得するデータの開始位置。デフォルトは 0。
                - limit (int): 取得するデータの件数。デフォルトは 10。
                - order_by (Callable | str): 結果を並べ替えるための呼び出し可能オブジェクト。デフォルトはモデルの id フィールドの降順。
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
        order_by = self.model.id.asc()

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

    def find(self, filters: Optional[List[Callable]] = None, include_deleted: bool = False, **kwargs) -> List[T]:
        """
        共通の find メソッド。特に指定が無ければ全件を取得する。
        取得量を絞りたい場合は、offset と limit を指定する。

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト。
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数。

        Returns:
            List[T]: モデルのリスト。
        """
        query = select(self.model)

        # 論理削除フィルタを追加
        all_filters = list(filters) if filters else []
        if self._has_soft_delete() and not include_deleted:
            all_filters.append(self.model.deleted_at.is_(None))

        if all_filters:
            query = query.where(and_(*all_filters))
        query = self.set_find_option(query, **kwargs)
        return self.session.execute(query).scalars().all()

    def find_one(self, filters: list, options: Optional[List] = None) -> Optional[T]:
        """
        Retrieve a single record based on the provided filters (SQLAlchemy expressions list).

        Args:
            filters (list): フィルタ条件のリスト。
            options (Optional[List]): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> item = repo.find_one(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)]
            ... )
        """
        query = select(self.model).filter(*filters).limit(1)

        # eager loading 対応
        if options:
            query = query.options(*options)

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

    def find_by_ids(
        self,
        ids: List[int],
        include_deleted: bool = False,
        **kwargs
    ) -> List[T]:
        """指定された ID のリストでレコードを一括取得

        N+1 問題を解決するための一括取得メソッド。
        複数のレコードを1回のクエリで取得します。

        Args:
            ids: 取得するレコードのIDリスト
            include_deleted: 削除済みも含めるか（デフォルト: False）
            **kwargs: order_by などのオプション

        Returns:
            List[T]: 見つかったレコードのリスト（順序は保証されない）

        使用例:
            # N+1問題を解決
            asset_ids = [link.asset_item_id for link in item.asset_links]
            assets = asset_repo.find_by_ids(asset_ids)

            # IDでマッピング作成
            asset_map = {a.id: a for a in assets}
            for link in item.asset_links:
                asset = asset_map.get(link.asset_item_id)
        """
        if not ids:
            return []

        # ID フィルタ
        filters = [self.model.id.in_(ids)]

        # 論理削除フィルタ
        if self._has_soft_delete() and not include_deleted:
            filters.append(self.model.deleted_at.is_(None))

        query = select(self.model).where(and_(*filters))
        query = self.set_find_option(query, **kwargs)
        return self.session.execute(query).scalars().all()

    # ========================================
    # 論理削除関連メソッド
    # ========================================

    def soft_delete(self, id: int) -> bool:
        """論理削除

        指定されたIDのレコードを論理削除します。
        deleted_at に現在時刻（UTC）を設定します。

        Args:
            id (int): 削除するレコードのID

        Returns:
            bool: 削除成功したか（レコードが見つからない場合は False）

        Raises:
            ValueError: モデルが SoftDeletableMixin を持たない場合

        使用例:
            repo = BaseRepository(MyModel)
            if repo.soft_delete(1):
                print("削除成功")
        """
        if not self._has_soft_delete():
            raise ValueError(
                f"{self.model.__name__} does not support soft delete. "
                "Add SoftDeletableMixin to the model."
            )

        item = self.get_by_id(id, include_deleted=False)
        if not item:
            return False

        item.soft_delete()
        try:
            self.session.commit()
            return True
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def restore(self, id: int) -> bool:
        """削除を復元

        論理削除されたレコードを復元します。
        deleted_at を NULL に戻します。

        Args:
            id (int): 復元するレコードのID

        Returns:
            bool: 復元成功したか（削除済みレコードが見つからない場合は False）

        Raises:
            ValueError: モデルが SoftDeletableMixin を持たない場合

        使用例:
            repo = BaseRepository(MyModel)
            if repo.restore(1):
                print("復元成功")
        """
        if not self._has_soft_delete():
            raise ValueError(
                f"{self.model.__name__} does not support soft delete."
            )

        item = self.get_by_id(id, include_deleted=True)
        if not item or not item.is_deleted:
            return False

        item.restore()
        try:
            self.session.commit()
            return True
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def permanent_delete(self, id: int) -> bool:
        """物理削除

        データベースからレコードを完全に削除します。
        削除済み（deleted_at が設定されている）レコードも対象です。

        Args:
            id (int): 削除するレコードのID

        Returns:
            bool: 削除成功したか（レコードが見つからない場合は False）

        注意:
            この操作は取り消せません。

        使用例:
            repo = BaseRepository(MyModel)
            if repo.permanent_delete(1):
                print("物理削除成功")
        """
        # 削除済みレコードも含めて取得
        if self._has_soft_delete():
            item = self.get_by_id(id, include_deleted=True)
        else:
            item = self.get_by_id(id)

        if not item:
            return False

        try:
            self.session.delete(item)
            self.session.commit()
            logger.warning(
                f"Permanently deleted: {self.model.__name__} id={id}"
            )
            return True
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def find_deleted(self, filters: Optional[List[Callable]] = None, **kwargs) -> List[T]:
        """削除済みレコードのみ取得

        deleted_at が設定されているレコードのみを検索します。
        バッチ処理などで削除済みデータを検索する際に使用します。

        Args:
            filters (Optional[List[Callable]]): 追加のフィルタ条件
            **kwargs: offset, limit, order_by などのオプション

        Returns:
            List[T]: 削除済みレコードのリスト（論理削除非対応モデルは空リスト）

        使用例:
            repo = BaseRepository(MyModel)
            deleted_items = repo.find_deleted()
        """
        if not self._has_soft_delete():
            return []

        all_filters = list(filters) if filters else []
        all_filters.append(self.model.deleted_at.isnot(None))

        query = select(self.model).where(and_(*all_filters))
        query = self.set_find_option(query, **kwargs)
        return self.session.execute(query).scalars().all()

    def find_deleted_before(self, before_date: datetime, **kwargs) -> List[T]:
        """指定日時より前に削除されたレコードを取得

        Args:
            before_date (datetime): この日時より前に削除されたレコードを検索
            **kwargs: offset, limit, order_by などのオプション

        Returns:
            List[T]: 条件に一致するレコードのリスト（論理削除非対応モデルは空リスト）

        使用例:
            from datetime import datetime, timedelta, timezone

            # 30日以上前に削除されたレコードを取得
            repo = BaseRepository(MyModel)
            threshold = datetime.now(timezone.utc) - timedelta(days=30)
            old_deleted = repo.find_deleted_before(threshold)

            # 物理削除
            for item in old_deleted:
                repo.permanent_delete(item.id)
        """
        if not self._has_soft_delete():
            return []

        filters = [
            self.model.deleted_at.isnot(None),
            self.model.deleted_at < before_date
        ]

        query = select(self.model).where(and_(*filters))
        query = self.set_find_option(query, **kwargs)
        return self.session.execute(query).scalars().all()
