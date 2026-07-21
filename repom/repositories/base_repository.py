from contextlib import contextmanager
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any, Callable, TypeVar, Generic, Optional, List, Dict, Union
from sqlalchemy import ColumnElement, and_, delete, func, select, true, update
from sqlalchemy.orm import Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from repom.database import get_db_session
from repom.repositories._core import FilterParams
from repom.repositories._repository_base import RepositoryBase
from repom.repositories._soft_delete import SoftDeleteRepositoryMixin
from repom.repositories._query_builder import QueryBuilderMixin
import logging

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class BaseRepository(RepositoryBase[T], SoftDeleteRepositoryMixin[T], QueryBuilderMixin[T], Generic[T]):
    """同期版ベースリポジトリ

    - RepositoryBase により同期/非同期共通のメンバー（__init__、session、
      _has_soft_delete、_bulk_filters、モデル推論）を継承
    - SoftDeleteRepositoryMixin により論理削除機能を提供
    - QueryBuilderMixin によりクエリ構築機能を提供（同期/非同期共通の実装）

    Example:
        # 明示的な model 指定（従来の方法）
        repo = BaseRepository(User, session=db_session)

        # __init__ を省略した子クラスで自動推論
        class UserRepository(BaseRepository[User]):
            pass

        repo = UserRepository(session=db_session)  # User が自動推論される
    """

    # RepositoryBase.__init__ のセッション種別ガード設定
    _session_reject_types = (Session, scoped_session)
    _session_reject_message = (
        "Session object was passed as 'model' parameter. "
        "This usually happens when __init__ is omitted and repo_class(session) is called. "
        "Please use 'session' parameter: repo_class(session=session) or define __init__ explicitly."
    )
    _repository_base_name = "BaseRepository"

    @contextmanager
    def _session_scope(self) -> Session:
        """セッション取得を一元化し、None の場合は get_db_session() で補完"""
        if self.session is not None:
            yield self.session
            return

        session_generator = get_db_session()
        session = next(session_generator)
        self._scoped_session = session
        try:
            yield session
        finally:
            if self._scoped_session is session:
                session.expunge_all()
            self._scoped_session = None
            session_generator.close()

    def get_by(
        self,
        column_name: str,
        value: Any,
        *extra_filters: ColumnElement,
        single: bool = False,
        include_deleted: bool = False,
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
            include_deleted: 削除済みレコードも含めるか（デフォルト: False）
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
        results = self._find_with_filters(
            filters,
            include_deleted=include_deleted,
            options=options,
            limit=1 if single else None,
            apply_order_by=not single,
        )
        if single:
            return results[0] if results else None
        return results

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
        if not hasattr(self.model, 'id'):
            raise AttributeError(f"Column 'id' does not exist on {self.model.__name__}")

        results = self._find_with_filters(
            [self.model.id == id],
            include_deleted=include_deleted,
            options=options,
            limit=1,
            apply_order_by=False,
        )
        return results[0] if results else None

    def get_all(self) -> List[T]:
        """
        全てのインスタンスを取得

        Returns:
            List[T]: 全てのインスタンスのリスト
        """
        with self._session_scope() as session:
            result = session.execute(self._base_select())
            return result.scalars().all()

    def save(self, instance: T) -> T:
        """
        インスタンスを保存

        Args:
            instance (T): 保存するインスタンス
        Returns:
            T: 保存したインスタンス

        Note:
            明示的なセッションが渡されている場合、refresh() は不要です。
            セッション未指定で内部セッションを生成した場合は、commit 後に refresh()
            を実行し、セッションを閉じても最新値を保持できるようにしています。

            非同期版（AsyncBaseRepository.save）では refresh() が必須です。
        """
        with self._session_scope() as session:
            using_internal_session = self._session_override is None and self._scoped_session is session
            try:
                session.add(instance)
                if using_internal_session:
                    session.commit()
                    session.refresh(instance)
                else:
                    session.flush()
            except SQLAlchemyError:
                if using_internal_session:
                    session.rollback()
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
            セッション未指定で内部セッションを生成した場合のみ refresh() を実行し、
            セッションを閉じた後でも最新値を保持します。
            非同期版（AsyncBaseRepository.saves）では各インスタンスの refresh() が必須です。
        """
        with self._session_scope() as session:
            using_internal_session = self._session_override is None and self._scoped_session is session
            try:
                session.add_all(instances)
                if using_internal_session:
                    session.commit()
                    for instance in instances:
                        session.refresh(instance)
                else:
                    session.flush()
            except SQLAlchemyError:
                if using_internal_session:
                    session.rollback()
                raise

    def dict_saves(self, data_list: List[Dict]) -> None:
        """
        Listの中に入ったdict型のデータをモデルインスタンスにして保存

        Args:
            data_list (List[Dict]): 保存するデータのリスト
        """
        instances = [self.model(**data) for data in data_list]
        self.saves(instances)

    def bulk_insert(self, objects: Sequence[T]) -> list[T]:
        """複数インスタンスを一括保存して、保存済みオブジェクトを返す。"""
        if not objects:
            return []

        instances = list(objects)
        with self._session_scope() as session:
            using_internal_session = self._session_override is None and self._scoped_session is session
            try:
                session.add_all(instances)
                if using_internal_session:
                    session.commit()
                    for instance in instances:
                        session.refresh(instance)
                else:
                    session.flush()
            except SQLAlchemyError:
                if using_internal_session:
                    session.rollback()
                raise
        return instances

    def bulk_update(self, values: Sequence[dict], *, filter_by: dict | None = None) -> int:
        """複数レコードを一括更新し、影響行数を返す。

        ``filter_by`` 未指定時は各 dict の ``id`` を条件として使います。
        ``filter_by`` 指定時は渡された条件に対して各 dict の値を適用します。
        """
        if not values:
            return 0

        if filter_by is None:
            for row in values:
                if "id" not in row:
                    raise ValueError("bulk_update() requires each values dict to include 'id' when filter_by is not provided.")

        with self._session_scope() as session:
            using_internal_session = self._session_override is None and self._scoped_session is session
            rowcount = 0
            try:
                for row in values:
                    update_values = dict(row)
                    filters = self._bulk_filters(filter_by)
                    if filter_by is None:
                        filters.append(self.model.id == update_values.pop("id"))
                    if not update_values:
                        continue

                    result = session.execute(
                        update(self.model)
                        .where(and_(*filters))
                        .values(**update_values)
                        .execution_options(synchronize_session="fetch")
                    )
                    rowcount += result.rowcount or 0

                if using_internal_session:
                    session.commit()
                else:
                    session.flush()
                session.expire_all()
            except SQLAlchemyError:
                if using_internal_session:
                    session.rollback()
                raise
        return rowcount

    def bulk_delete(self, *, filter_by: dict | None = None, ids: Sequence[Any] | None = None) -> int:
        """条件に一致するレコードを一括削除し、影響行数を返す。

        SoftDeletableMixin 対応モデルでは ``deleted_at`` を更新し、非対応モデルでは
        物理削除します。``filter_by`` と ``ids`` を省略すると全件が対象です。
        """
        filters = self._bulk_filters(filter_by)
        if ids is not None:
            if not ids:
                return 0
            filters.append(self.model.id.in_(ids))

        with self._session_scope() as session:
            using_internal_session = self._session_override is None and self._scoped_session is session
            try:
                if self._has_soft_delete():
                    filters.append(self.model.deleted_at.is_(None))
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
                result = session.execute(statement)
                rowcount = result.rowcount or 0
                if using_internal_session:
                    session.commit()
                else:
                    session.flush()
                session.expire_all()
            except SQLAlchemyError:
                if using_internal_session:
                    session.rollback()
                raise
        return rowcount

    def remove(self, instance: T) -> None:
        """
        インスタンスを削除

        Args:
            instance (T): 削除するインスタンス
        """
        with self._session_scope() as session:
            using_internal_session = self._session_override is None and self._scoped_session is session
            try:
                managed_instance = session.merge(instance)
                session.delete(managed_instance)
                if using_internal_session:
                    session.commit()
                else:
                    session.flush()
            except SQLAlchemyError:
                if using_internal_session:
                    session.rollback()
                raise

    def find(
        self,
        params: Optional[FilterParams] = None,
        filters: Optional[List[Callable]] = None,
        include_deleted: bool = False,
        **kwargs
    ) -> List[T]:
        """
        共通の find メソッド。特に指定が無ければ全件を取得する。
        取得量を絞りたい場合は、offset と limit を指定する。

        Args:
            params (Optional[FilterParams]): FilterParams からフィルタを生成するためのパラメータ。
            filters (Optional[List[Callable]]): フィルタ条件のリスト。
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数
                - offset (int): 取得開始位置
                - limit (int): 取得件数
                - order_by (str | UnaryExpression): ソート順
                - options (list | Load): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            List[T]: モデルのリスト。

        Overrides must accept and merge ``filters`` and ``include_deleted``.
        Callers rely on those arguments to constrain results and enforce the
        soft-delete policy.
        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> # 複数レコード取得（relationship も eager load）
            >>> items = repo.find(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)],
            ...     limit=10
            ... )
        """
        query = self._base_select()

        # 論理削除フィルタを追加
        base_filters = filters if filters is not None else self._build_filters(params)
        all_filters = list(base_filters) if base_filters else []
        if self._has_soft_delete() and not include_deleted:
            all_filters.append(self.model.deleted_at.is_(None))

        if all_filters:
            query = query.where(and_(*all_filters))

        query = self.set_find_option(query, **kwargs)
        with self._session_scope() as session:
            return session.execute(query).scalars().all()

    def _find_with_filters(
        self,
        filters: list,
        *,
        include_deleted: bool,
        **kwargs,
    ) -> List[T]:
        query = self._base_select()
        all_filters = list(filters)
        if self._has_soft_delete() and not include_deleted:
            all_filters.append(self.model.deleted_at.is_(None))

        if all_filters:
            query = query.where(and_(*all_filters))

        query = self.set_find_option(query, **kwargs)
        with self._session_scope() as session:
            return session.execute(query).scalars().all()

    def find_one(self, filters: list, include_deleted: bool = False, **kwargs) -> Optional[T]:
        """
        find の最初の1件取得版

        Args:
            filters (list): フィルタ条件のリスト。
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            **kwargs: 任意のキーワード引数（options など）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone

        Example:
            >>> from sqlalchemy.orm import selectinload
            >>> item = repo.find_one(
            ...     filters=[Model.status == 'active'],
            ...     options=[selectinload(Model.tags)]
            ... )
        """
        kwargs["limit"] = 1
        results = self._find_with_filters(filters, include_deleted=include_deleted, **kwargs)
        return results[0] if results else None

    def count(self, filters: Optional[List[Callable]] = None, include_deleted: bool = False) -> int:
        """
        指定したフィルタ条件に一致するレコード数を返す

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト。
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）

        Returns:
            int: 一致するレコード数
        """
        query = select(func.count()).select_from(self.model)
        all_filters = list(filters) if filters else []
        if self._has_soft_delete() and not include_deleted:
            all_filters.append(self.model.deleted_at.is_(None))

        if all_filters:
            query = query.where(and_(*all_filters))
        with self._session_scope() as session:
            return session.execute(query).scalar()

    def count_by_params(self, params: Optional[FilterParams] = None, include_deleted: bool = False) -> int:
        filters = self._build_filters(params)
        return self.count(filters=filters, include_deleted=include_deleted)

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

        query = self._base_select().where(and_(*filters))
        query = self.set_find_option(query, **kwargs)
        with self._session_scope() as session:
            return session.execute(query).scalars().all()
