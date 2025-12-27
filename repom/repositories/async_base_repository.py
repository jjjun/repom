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

from contextlib import asynccontextmanager
from typing import Any, Callable, Type, TypeVar, Generic, Optional, List, Dict, Union
from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from repom.database import get_async_db_session
from repom.repositories._core import has_soft_delete, FilterParams
from repom.repositories._soft_delete import AsyncSoftDeleteRepositoryMixin
from repom.repositories._query_builder import QueryBuilderMixin
import logging

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class AsyncBaseRepository(AsyncSoftDeleteRepositoryMixin[T], QueryBuilderMixin[T], Generic[T]):
    """非同期版のベースリポジトリ

    BaseRepository と同じ機能を非同期で提供します。
    すべてのメソッドは async def で定義されています。

    Attributes:
        allowed_order_columns: ソート可能なカラムのホワイトリスト（サブクラスで拡張可能、同期/非同期共通）
    """

    def __init__(self, model: Type[T], session: Optional[AsyncSession] = None):
        """AsyncBaseRepository の初期化

        Args:
            model (Type[T]): モデルクラス
            session (AsyncSession, optional): 非同期データベースセッション. Defaults to None (get_async_db_session() を使用).
        """
        self.model = model
        self._session_override = session
        self._scoped_session: Optional[AsyncSession] = None

    @property
    def session(self) -> Optional[AsyncSession]:
        """明示的に渡されたセッション（またはスコープ内の内部セッション）を返却"""
        return self._session_override or self._scoped_session

    @session.setter
    def session(self, session: Optional[AsyncSession]) -> None:
        """明示的セッションを設定（None でリセット）"""
        self._session_override = session

    @asynccontextmanager
    async def _session_scope(self) -> AsyncSession:
        """セッション取得を一元化し、None の場合は get_async_db_session() で補完"""
        if self.session is not None:
            yield self.session
            return

        session_generator = get_async_db_session()
        session = await anext(session_generator)
        self._scoped_session = session
        try:
            yield session
        finally:
            if self._scoped_session is session:
                session.expunge_all()
            self._scoped_session = None
            await session_generator.aclose()

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
        include_deleted: bool = False,
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
            include_deleted: 削除済みレコードも含めるか（デフォルト: False）
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
            return await self.find_one(filters=filters, include_deleted=include_deleted, options=options)
        return await self.find(filters=filters, include_deleted=include_deleted, options=options)

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
        return await self.get_by('id', id, single=True, include_deleted=include_deleted, options=options)

    async def get_all(self) -> List[T]:
        """全てのインスタンスを取得

        Returns:
            List[T]: 全てのインスタンスのリスト
        """
        async with self._session_scope() as session:
            result = await session.execute(select(self.model))
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
        async with self._session_scope() as session:
            try:
                session.add(instance)
                await session.commit()
                # 非同期環境では refresh() が必須（AutoDateTime等のDB自動設定値を反映）
                await session.refresh(instance)
            except SQLAlchemyError:
                await session.rollback()
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
        async with self._session_scope() as session:
            try:
                session.add_all(instances)
                await session.commit()
                # 非同期環境では各インスタンスの refresh() が必須
                for instance in instances:
                    await session.refresh(instance)
            except SQLAlchemyError:
                await session.rollback()
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
        async with self._session_scope() as session:
            try:
                managed_instance = await session.merge(instance)
                await session.delete(managed_instance)
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                raise

    async def find(
        self,
        filters: Optional[List[Callable]] = None,
        include_deleted: bool = False,
        **kwargs
    ) -> List[T]:
        """共通の find メソッド

        特に指定が無ければ全件を取得する。
        取得量を絞りたい場合は、offset と limit を指定する。

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数
                - offset (int): 取得開始位置
                - limit (int): 取得件数
                - order_by (str | UnaryExpression): ソート順
                - options (list | Load): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            List[T]: モデルのリスト

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> # 複数レコード取得（relationship も eager load）
            >>> items = await repo.find(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)],
            ...     limit=10
            ... )
        """
        query = select(self.model)

        # 論理削除フィルタを追加
        all_filters = list(filters) if filters else []
        if self._has_soft_delete() and not include_deleted:
            all_filters.append(self.model.deleted_at.is_(None))

        if all_filters:
            query = query.where(and_(*all_filters))

        query = self.set_find_option(query, **kwargs)
        async with self._session_scope() as session:
            result = await session.execute(query)
            return result.scalars().all()

    async def find_one(self, filters: list, include_deleted: bool = False, **kwargs) -> Optional[T]:
        """find の最初の1件取得版

        Args:
            filters (list): フィルタ条件のリスト
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数（options など）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> item = await repo.find_one(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)]
            ... )
        """
        results = await self.find(filters=filters, include_deleted=include_deleted, limit=1, **kwargs)
        return results[0] if results else None

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
        async with self._session_scope() as session:
            result = await session.execute(query)
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
        async with self._session_scope() as session:
            result = await session.execute(query)
            return result.scalars().all()
