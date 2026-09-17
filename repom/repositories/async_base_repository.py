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
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any, Callable, TypeVar, Generic, Optional, List, Dict, Union
from sqlalchemy import ColumnElement, and_, delete, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session
from sqlalchemy.exc import SQLAlchemyError
from repom.database import get_async_db_session
from repom.nul_bytes import validate_values_no_nul_bytes
from repom.repositories._core import FilterParams
from repom.repositories._repository_base import RepositoryBase
from repom.repositories._soft_delete import AsyncSoftDeleteRepositoryMixin
from repom.repositories._query_builder import QueryBuilderMixin
import logging
import warnings

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class AsyncBaseRepository(RepositoryBase[T], AsyncSoftDeleteRepositoryMixin[T], QueryBuilderMixin[T], Generic[T]):
    """非同期版のベースリポジトリ

    BaseRepository と同じ機能を非同期で提供します。
    すべての I/O メソッドは async def で定義されています。
    同期/非同期共通のメンバー（__init__、session、_has_soft_delete、
    _bulk_filters、モデル推論）は RepositoryBase から継承します。

    Attributes:
        allowed_order_columns: ソート可能なカラムのホワイトリスト（サブクラスで拡張可能、同期/非同期共通）

    Example:
        # 明示的な model 指定（従来の方法）
        repo = AsyncBaseRepository(User, session=async_session)

        # __init__ を省略した子クラスで自動推論
        class UserRepository(AsyncBaseRepository[User]):
            pass

        repo = UserRepository(session=async_session)  # User が自動推論される
    """

    # RepositoryBase.__init__ のセッション種別ガード設定
    _session_reject_types = (AsyncSession, async_scoped_session)
    _session_reject_message = (
        "AsyncSession object was passed as 'model' parameter. "
        "This usually happens when __init__ is omitted and repo_class(session) is called. "
        "Please use 'session' parameter: repo_class(session=session) or define __init__ explicitly."
    )
    _repository_base_name = "AsyncBaseRepository"

    @asynccontextmanager
    async def _session_scope(self) -> AsyncSession:
        """セッション取得を一元化し、None の場合は get_async_db_session() で補完"""
        if self.session is not None:
            yield self.session
            return

        session_generator = get_async_db_session()
        session = await anext(session_generator)
        token = self._scoped_session_var.set(session)
        try:
            yield session
        finally:
            session.expunge_all()
            self._scoped_session_var.reset(token)
            await session_generator.aclose()

    @asynccontextmanager
    async def _commit_or_flush(self, session):
        """内部セッションは commit、外部セッションは flush する共通処理。

        save / saves / bulk_insert / bulk_update / bulk_delete / remove と
        soft_delete / restore / permanent_delete（_soft_delete.py）に共通する
        書き込み系の commit-flush-rollback パターンを一元化するコンテキスト
        マネージャ。SQLAlchemyError が発生した場合は内部セッションのみ
        rollback してから re-raise する（外部セッションの rollback は呼び出し
        元の責任のため行わない）。

        Args:
            session: 対象のセッション（_session_scope() で取得したもの）

        Yields:
            bool: session が _session_scope() の内部生成セッションかどうか
                （using_internal_session）。commit/flush 後の後処理
                （refresh など）を内部セッション限定にする際に使う。
        """
        using_internal_session = self._uses_internal_session(session)
        try:
            yield using_internal_session
            if using_internal_session:
                await session.commit()
            else:
                await session.flush()
        except SQLAlchemyError:
            if using_internal_session:
                await session.rollback()
            raise

    async def _execute_scalars_unique(self, query) -> List[T]:
        """モデルエンティティを返す SELECT を実行し、重複のない結果を返す。

        コレクションに対する joinedload はエンティティごとに行が重複し、
        SQLAlchemy はその場合 Result.unique() の呼び出しを要求する
        （呼ばないと InvalidRequestError になる）。unique() はそれ以外の
        クエリでは無害な no-op なので、常に呼んでよい。副作用として、
        _base_select() を override して一対多の関連を eager load せずに
        JOIN した場合の重複行も同様に排除される。
        """
        async with self._session_scope() as session:
            result = await session.execute(query)
            return result.scalars().unique().all()

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
            column_name: 検索するカラム名。信頼できる識別子であることが前提。
                リクエストのフィールド名をそのまま渡すなど、信頼できない
                入力から導出する場合は allowed_filter_columns でホワイト
                リストを設定すること。
            value: 検索する値
            extra_filters: 追加のフィルタ条件
            single: True の場合は最初の1件のみ返す
            include_deleted: 削除済みレコードも含めるか（デフォルト: False）
            options: SQLAlchemy クエリオプション（eager loading等）

        Returns:
            Union[List[T], Optional[T]]: レコードのリストまたは単一レコード

        Raises:
            AttributeError: 指定されたカラムがモデルに存在しない場合、または
                allowed_filter_columns によって許可されていない場合

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> # 単一レコード取得（relationship も eager load）
            >>> item = await repo.get_by(
            ...     'email', 'user@example.com',
            ...     single=True,
            ...     options=[selectinload(User.profile)]
            ... )
        """
        filters = [self._resolve_equality_filter(column_name, value), *extra_filters]
        results = await self._find_with_filters(
            filters,
            include_deleted=include_deleted,
            options=options,
            limit=1 if single else None,
            apply_order_by=not single,
        )
        if single:
            return results[0] if results else None
        return results

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
        if not hasattr(self.model, 'id'):
            raise AttributeError(f"Column 'id' does not exist on {self.model.__name__}")

        results = await self._find_with_filters(
            [self.model.id == id],
            include_deleted=include_deleted,
            options=options,
            limit=1,
            apply_order_by=False,
        )
        return results[0] if results else None

    async def get_all(self, include_deleted: bool = False) -> List[T]:
        """全てのインスタンスを取得

        Args:
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）

        Returns:
            List[T]: 全てのインスタンスのリスト
        """
        return await self._find_with_filters([], include_deleted=include_deleted)

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
            async with self._commit_or_flush(session) as using_internal_session:
                session.add(instance)
            if using_internal_session:
                # 非同期環境では refresh() が必須（AutoDateTime等のDB自動設定値を反映）
                await session.refresh(instance)
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
            async with self._commit_or_flush(session) as using_internal_session:
                session.add_all(instances)
            if using_internal_session:
                # 非同期環境では各インスタンスの refresh() が必須
                for instance in instances:
                    await session.refresh(instance)

    async def dict_saves(self, data_list: List[Dict]) -> None:
        """Listの中に入ったdict型のデータをモデルインスタンスにして保存

        Args:
            data_list (List[Dict]): 保存するデータのリスト
        """
        instances = [self.model(**data) for data in data_list]
        await self.saves(instances)

    async def bulk_insert(self, objects: Sequence[T]) -> list[T]:
        """複数インスタンスを一括保存して、保存済みオブジェクトを返す。"""
        if not objects:
            return []

        instances = list(objects)
        async with self._session_scope() as session:
            async with self._commit_or_flush(session) as using_internal_session:
                session.add_all(instances)
            if using_internal_session:
                for instance in instances:
                    await session.refresh(instance)
        return instances

    async def bulk_update(
        self, values: Sequence[dict], *, filter_by: dict | None = None, allow_unfiltered: bool = False
    ) -> int:
        """複数レコードを一括更新し、影響行数を返す。

        ``filter_by`` 未指定時は各 dict の ``id`` を条件として使います。
        ``filter_by`` 指定時は渡された条件に対して各 dict の値を適用します。
        ``filter_by`` に空の dict を渡すと全件が対象になるため、
        ``allow_unfiltered=True`` を明示しない限り ``ValueError`` を送出します。
        """
        if not values:
            return 0

        if filter_by is None:
            for row in values:
                if "id" not in row:
                    raise ValueError("bulk_update() requires each values dict to include 'id' when filter_by is not provided.")
        elif not filter_by and not allow_unfiltered:
            raise ValueError(
                "bulk_update() requires a non-empty filter_by, or allow_unfiltered=True "
                "to update every row matched by filter_by."
            )

        async with self._session_scope() as session:
            rowcount = 0
            async with self._commit_or_flush(session):
                for row in values:
                    update_values = dict(row)
                    filters = self._bulk_filters(filter_by)
                    if filter_by is None:
                        filters.append(self.model.id == update_values.pop("id"))
                    if not update_values:
                        continue

                    validate_values_no_nul_bytes(self.model, update_values)

                    result = await session.execute(
                        update(self.model)
                        .where(and_(*filters) if filters else true())
                        .values(**update_values)
                        .execution_options(synchronize_session="fetch")
                    )
                    rowcount += result.rowcount or 0
            # 同期版と異なり expire_all() は呼ばない: AsyncSession では expire された
            # 属性への遅延ロードが同期的な I/O を要求して失敗するため。
        return rowcount

    async def bulk_delete(
        self,
        *,
        filter_by: dict | None = None,
        ids: Sequence[Any] | None = None,
        allow_unfiltered: bool = False,
    ) -> int:
        """条件に一致するレコードを一括削除し、影響行数を返す。

        SoftDeletableMixin 対応モデルでは ``deleted_at`` を更新し、非対応モデルでは
        物理削除します。``filter_by`` と ``ids`` を両方省略すると絞り込みが無くなる
        ため、``allow_unfiltered=True`` を明示しない限り ``ValueError`` を送出します。
        """
        filters = self._bulk_filters(filter_by)
        if ids is not None:
            if not ids:
                return 0
            filters.append(self._resolve_ids_filter(ids))

        if not filters and not allow_unfiltered:
            raise ValueError(
                "bulk_delete() requires filter_by or ids, or allow_unfiltered=True "
                "to delete every row."
            )

        async with self._session_scope() as session:
            rowcount = 0
            async with self._commit_or_flush(session):
                if self._has_soft_delete():
                    self._append_soft_delete_filter(filters)
                    statement = (
                        update(self.model)
                        .where(and_(*filters) if filters else true())
                        .values(deleted_at=datetime.now(timezone.utc))
                        .execution_options(synchronize_session="fetch")
                    )
                else:
                    statement = (
                        delete(self.model)
                        .where(and_(*filters) if filters else true())
                        .execution_options(synchronize_session="fetch")
                    )
                result = await session.execute(statement)
                rowcount = result.rowcount or 0
            # 同期版と異なり expire_all() は呼ばない: AsyncSession では expire された
            # 属性への遅延ロードが同期的な I/O を要求して失敗するため。
        return rowcount

    async def remove(self, instance: T) -> None:
        """インスタンスを削除

        Args:
            instance (T): 削除するインスタンス
        """
        async with self._session_scope() as session:
            async with self._commit_or_flush(session):
                managed_instance = await session.merge(instance)
                await session.delete(managed_instance)

    async def find(
        self,
        params: Optional[FilterParams] = None,
        filters: Optional[List[Callable]] = None,
        include_deleted: bool = False,
        **kwargs
    ) -> List[T]:
        """共通の find メソッド

        特に指定が無ければ全件を取得する。
        取得量を絞りたい場合は、offset と limit を指定する。

        Args:
            params (Optional[FilterParams]): FilterParams からフィルタを生成するためのパラメータ。
            filters (Optional[List[Callable]]): フィルタ条件のリスト
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数
                - offset (int): 取得開始位置
                - limit (int): 取得件数
                - order_by (str | UnaryExpression): ソート順
                - options (list | Load): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            List[T]: モデルのリスト

        Overrides must accept and merge ``filters`` and ``include_deleted``.
        Callers rely on those arguments to constrain results and enforce the
        soft-delete policy.

        Results are deduplicated via ``Result.unique()``, so ``options`` may
        include a ``joinedload()`` of a collection relationship (each parent
        is returned once with its full collection) in addition to scalar
        joinedload/selectinload.
        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> # 複数レコード取得（relationship も eager load）
            >>> items = await repo.find(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)],
            ...     limit=10
            ... )
        """
        if kwargs.get('limit', None) is None:
            warnings.warn(
                "find() was called without a limit; the query will return "
                "every matching row. Pass an explicit limit to bound the result size.",
                RuntimeWarning,
                stacklevel=2,
            )

        base_filters = filters if filters is not None else self._build_filters(params)
        return await self._find_with_filters(base_filters, include_deleted=include_deleted, **kwargs)

    async def _find_with_filters(
        self,
        filters: list,
        *,
        include_deleted: bool,
        **kwargs,
    ) -> List[T]:
        query = self._base_select()
        all_filters = list(filters)
        self._append_soft_delete_filter(all_filters, include_deleted)

        if all_filters:
            query = query.where(and_(*all_filters))

        query = self.set_find_option(query, **kwargs)
        return await self._execute_scalars_unique(query)

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
        kwargs["limit"] = 1
        results = await self._find_with_filters(filters, include_deleted=include_deleted, **kwargs)
        return results[0] if results else None

    async def count(self, filters: Optional[List[Callable]] = None, include_deleted: bool = False) -> int:
        """指定したフィルタ条件に一致するレコード数を返す

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）

        Returns:
            int: 一致するレコード数
        """
        from sqlalchemy import func

        query = select(func.count()).select_from(self.model)
        all_filters = list(filters) if filters else []
        self._append_soft_delete_filter(all_filters, include_deleted)

        if all_filters:
            query = query.where(and_(*all_filters))
        async with self._session_scope() as session:
            result = await session.execute(query)
            return result.scalar()

    async def count_by_params(self, params: Optional[FilterParams] = None, include_deleted: bool = False) -> int:
        """FilterParams によるレコード数カウント

        Args:
            params: フィルタパラメータ
            include_deleted: 削除済みレコードも含めるか（デフォルト: False）

        Returns:
            int: 一致するレコード数
        """
        filters = self._build_filters(params)
        return await self.count(filters=filters, include_deleted=include_deleted)

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
        return await self._find_with_filters(filters, include_deleted=include_deleted, **kwargs)
