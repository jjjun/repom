"""
Async Repository Pattern for repom.

Provides AsyncBaseRepository for asynchronous database operations.
Compatible with FastAPI, AsyncSession, and modern async patterns.

Example:
    >>> from repom.async_base_repository import AsyncBaseRepository
    >>> from repom.async_session import get_async_db_session
    >>> 
    >>> class AsyncUserRepository(AsyncBaseRepository[User]):
    >>>     pass
    >>> 
    >>> @app.get("/users")
    >>> async def get_users(session: AsyncSession = Depends(get_async_db_session)):
    >>>     repo = AsyncUserRepository(User, session)
    >>>     users = await repo.find(
    >>>         filters=[User.status == 'active'],
    >>>         options=[joinedload(User.profile)]
    >>>     )
    >>>     return users
"""

from typing import Any, Callable, Type, TypeVar, Generic, Optional, List, Dict, Union
from datetime import datetime
from sqlalchemy import ColumnElement, UnaryExpression, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from repom.repositories._core import has_soft_delete, parse_order_by, set_find_option, FilterParams
from repom.repositories._soft_delete import AsyncSoftDeleteRepositoryMixin
import logging

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class AsyncBaseRepository(AsyncSoftDeleteRepositoryMixin[T], Generic[T]):
    """非同期版のベースリポジトリ

    BaseRepository と同じ機能を非同期で提供します。
    すべてのメソッドは async def で定義されています。

    Attributes:
        allowed_order_columns: ソート可能なカラムのホワイトリスト（サブクラスで拡張可能）
    """

    # Default allowed columns for order_by operations (can be extended by subclasses)
    allowed_order_columns = [
        'id', 'title', 'created_at', 'updated_at',
        'started_at', 'finished_at', 'executed_at'
    ]

    def __init__(self, model: Type[T], session: AsyncSession):
        """AsyncBaseRepository の初期化

        Args:
            model (Type[T]): モデルクラス
            session (AsyncSession): 非同期データベースセッション
        """
        self.model = model
        self.session = session

    def _has_soft_delete(self) -> bool:
        """モデルが SoftDeletableMixin を持つか確認

        Returns:
            bool: deleted_at カラムが存在する場合 True
        """
        return has_soft_delete(self.model)

    async def get_by(
        self,
        column_name: str,
        value: Any,
        *extra_filters: ColumnElement,
        single: bool = False,
        options: Optional[List] = None
    ) -> Union[List[T], Optional[T]]:
        """指定されたカラム名と値でレコードを取得

        追加のSQLAlchemyフィルタ式を ``extra_filters`` で指定できます。
        デフォルトでは一致する全てのレコードを返します。
        ``single`` が ``True`` の場合は最初の1件のみを返します。

        Args:
            column_name: 検索するカラム名
            value: 検索する値
            extra_filters: 追加のフィルタ条件
            single: True の場合は最初の1件のみ返す
            options: SQLAlchemy クエリオプション（eager loading等）

        Returns:
            Union[List[T], Optional[T]]: レコードのリストまたは単一レコード

        Raises:
            AttributeError: 指定されたカラムがモデルに存在しない場合

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> # 単一レコード取得（relationship も eager load）
            >>> item = await repo.get_by(
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
            return await self.find_one(filters=filters, options=options)
        return await self.find(filters=filters, options=options)

    async def get_by_id(self, id: int, include_deleted: bool = False, options: Optional[List] = None) -> Optional[T]:
        """指定されたIDのインスタンスを取得

        Args:
            id (int): インスタンスのID
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            options (Optional[List]): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone

        Example:
            >>> # シンプルな取得（従来通り）
            >>> item = await repo.get_by_id(123)
            >>> 
            >>> # relationship も一緒に取得（N+1問題を回避）
            >>> from sqlalchemy.orm import selectinload
            >>> item = await repo.get_by_id(123, options=[
            ...     selectinload(Model.tags),
            ...     selectinload(Model.reviews)
            ... ])
        """
        extra_filters = []
        if self._has_soft_delete() and not include_deleted:
            extra_filters.append(self.model.deleted_at.is_(None))

        return await self.get_by('id', id, *extra_filters, single=True, options=options)

    async def get_all(self) -> List[T]:
        """全てのインスタンスを取得

        Returns:
            List[T]: 全てのインスタンスのリスト
        """
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def save(self, instance: T) -> T:
        """インスタンスを保存

        Args:
            instance (T): 保存するインスタンス
        Returns:
            T: 保存したインスタンス（データベースの最新値で更新済み）

        Note:
            非同期セッションでは commit() 後に refresh() が必須です。
            理由: SQLAlchemy の非同期環境では、expire された属性への自動ロードが動作せず、
                  AutoDateTime などのデフォルト値が Python オブジェクトに反映されません。

            同期版（BaseRepository.save）では refresh() は不要です。
            理由: expire_on_commit=True (デフォルト) により、commit() 後に属性アクセス時
                  自動的にデータベースから再読み込みが発生するため。
        """
        try:
            self.session.add(instance)
            await self.session.commit()
            # 非同期環境では refresh() が必須（AutoDateTime等のDB自動設定値を反映）
            await self.session.refresh(instance)
        except SQLAlchemyError:
            await self.session.rollback()
            raise
        return instance

    async def dict_save(self, data: Dict) -> T:
        """dict型のデータをモデルインスタンスにして保存

        Args:
            data (Dict): 保存するデータ
        Returns:
            T: 保存したインスタンス
        """
        instance = self.model(**data)
        return await self.save(instance)

    async def saves(self, instances: List[T]) -> None:
        """Listの中に入ったインスタンスを保存

        Args:
            instances (List[T]): 保存するインスタンスのリスト

        Note:
            非同期セッションでは commit() 後に各インスタンスの refresh() が必須です。
            大量データの一括保存でパフォーマンスが問題になる場合は、
            保存後に get_by_id() で再取得する方法も検討してください。
        """
        try:
            self.session.add_all(instances)
            await self.session.commit()
            # 非同期環境では各インスタンスの refresh() が必須
            for instance in instances:
                await self.session.refresh(instance)
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def dict_saves(self, data_list: List[Dict]) -> None:
        """Listの中に入ったdict型のデータをモデルインスタンスにして保存

        Args:
            data_list (List[Dict]): 保存するデータのリスト
        """
        instances = [self.model(**data) for data in data_list]
        await self.saves(instances)

    async def remove(self, instance: T) -> None:
        """インスタンスを削除

        Args:
            instance (T): 削除するインスタンス
        """
        try:
            await self.session.delete(instance)
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    def set_find_option(self, query, **kwargs):
        """クエリにオプションを設定するメソッド（_core.set_find_option を呼び出し）

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
        """FilterParams からフィルタ条件を構築

        サブクラスでオーバーライドして独自のフィルタロジックを実装できます。

        Args:
            params: フィルタパラメータ

        Returns:
            list: フィルタ条件のリスト
        """
        # デフォルトは何もフィルタしない
        return []

    async def find(self, filters: Optional[List[Callable]] = None, include_deleted: bool = False, **kwargs) -> List[T]:
        """共通の find メソッド

        特に指定が無ければ全件を取得する。
        取得量を絞りたい場合は、offset と limit を指定する。

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数（offset, limit, order_by, options）

        Returns:
            List[T]: モデルのリスト
        """
        query = select(self.model)

        # 論理削除フィルタを追加
        all_filters = list(filters) if filters else []
        if self._has_soft_delete() and not include_deleted:
            all_filters.append(self.model.deleted_at.is_(None))

        if all_filters:
            query = query.where(and_(*all_filters))
        query = self.set_find_option(query, **kwargs)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def find_one(self, filters: list, options: Optional[List] = None) -> Optional[T]:
        """指定されたフィルタ条件で単一レコードを取得

        Args:
            filters (list): フィルタ条件のリスト
            options (Optional[List]): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> item = await repo.find_one(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)]
            ... )
        """
        query = select(self.model).filter(*filters).limit(1)

        # eager loading 対応
        if options:
            query = query.options(*options)

        result = await self.session.execute(query)
        return result.scalars().first()

    async def count(self, filters: Optional[List[Callable]] = None) -> int:
        """指定したフィルタ条件に一致するレコード数を返す

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト

        Returns:
            int: 一致するレコード数
        """
        from sqlalchemy import func

        query = select(func.count()).select_from(self.model)
        if filters:
            query = query.where(and_(*filters))
        result = await self.session.execute(query)
        return result.scalar()

    async def count_by_params(self, params: Optional[FilterParams] = None) -> int:
        """FilterParams によるレコード数カウント

        Args:
            params: フィルタパラメータ

        Returns:
            int: 一致するレコード数
        """
        filters = self._build_filters(params) if params else []
        return await self.count(filters=filters)

    async def find_by_ids(
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
            **kwargs: order_by, options などのオプション

        Returns:
            List[T]: 見つかったレコードのリスト（順序は保証されない）

        使用例:
            # N+1問題を解決
            asset_ids = [link.asset_item_id for link in item.asset_links]
            assets = await asset_repo.find_by_ids(asset_ids)

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
        result = await self.session.execute(query)
        return result.scalars().all()
