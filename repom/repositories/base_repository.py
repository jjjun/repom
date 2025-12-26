from typing import Any, Callable, Type, TypeVar, Generic, Optional, List, Dict, Union
from datetime import datetime
from sqlalchemy import ColumnElement, UnaryExpression, and_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from repom.repositories._core import has_soft_delete, parse_order_by, set_find_option, FilterParams
from repom.repositories._soft_delete import SoftDeleteRepositoryMixin
import logging

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class BaseRepository(SoftDeleteRepositoryMixin[T],Generic[T]):
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
        return has_soft_delete(self.model)

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
        クエリにオプションを設定するメソッド（_core.set_find_option を呼び出し）

        Args:
            query: SQLAlchemy のクエリオブジェクト
            **kwargs: offset, limit, order_by, options

        Returns:
            オプション設定済みのクエリオブジェクト
        """
        return set_find_option(query, self.model, self.allowed_order_columns, **kwargs)

    def parse_order_by(self, model_class, order_by_str: str):
        """Parse order_by string（_core.parse_order_by を呼び出し）

        Args:
            model_class: The SQLAlchemy model class
            order_by_str: Order specification string (e.g., "created_at:desc")

        Returns:
            SQLAlchemy column expression with asc() or desc()
        """
        return parse_order_by(model_class, order_by_str, self.allowed_order_columns)

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

