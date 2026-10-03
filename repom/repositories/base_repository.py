from contextlib import contextmanager
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any, Callable, TypeVar, Generic, Optional, List, Dict, Union
from sqlalchemy import ColumnElement, and_, delete, func, select, true, update
from sqlalchemy.orm import Session, scoped_session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from repom.database import get_db_session
from repom.exceptions import is_unique_violation
from repom.nul_bytes import validate_values_no_nul_bytes
from repom.repositories._core import FilterParams, _primary_key_order
from repom.repositories._repository_base import RepositoryBase
from repom.repositories._soft_delete import SoftDeleteRepositoryMixin
from repom.repositories._query_builder import QueryBuilderMixin
import logging
import warnings

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
        token = self._scoped_session_var.set(session)
        try:
            yield session
        finally:
            session.expunge_all()
            self._scoped_session_var.reset(token)
            session_generator.close()

    @contextmanager
    def _commit_or_flush(self, session):
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
                （refresh・expire_all など）を内部セッション限定にする際に使う。
        """
        using_internal_session = self._uses_internal_session(session)
        try:
            yield using_internal_session
            if using_internal_session:
                session.commit()
            else:
                session.flush()
        except SQLAlchemyError:
            if using_internal_session:
                session.rollback()
            raise

    def _execute_scalars_unique(self, query) -> List[T]:
        """モデルエンティティを返す SELECT を実行し、重複のない結果を返す。

        コレクションに対する joinedload はエンティティごとに行が重複し、
        SQLAlchemy はその場合 Result.unique() の呼び出しを要求する
        （呼ばないと InvalidRequestError になる）。unique() はそれ以外の
        クエリでは無害な no-op なので、常に呼んでよい。副作用として、
        _base_select() を override して一対多の関連を eager load せずに
        JOIN した場合の重複行も同様に排除される。
        """
        with self._session_scope() as session:
            return session.execute(query).scalars().unique().all()

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
            column_name: 検索するカラム名。信頼できる識別子であることが前提。
                リクエストのフィールド名をそのまま渡すなど、信頼できない
                入力から導出する場合は allowed_filter_columns でホワイト
                リストを設定すること。
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
        filters = [self._resolve_equality_filter(column_name, value), *extra_filters]
        results = self._find_with_filters(
            filters,
            include_deleted=include_deleted,
            options=options,
            limit=1 if single else None,
            order_by=_primary_key_order(self.model) if single else None,
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

        self._validate_value_only(id, "id")
        results = self._find_with_filters(
            [self.model.id == id],
            include_deleted=include_deleted,
            options=options,
            limit=1,
            apply_order_by=False,
        )
        return results[0] if results else None

    def get_all(self, include_deleted: bool = False) -> List[T]:
        """
        全てのインスタンスを取得

        Args:
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）

        Returns:
            List[T]: 全てのインスタンスのリスト
        """
        return self._find_with_filters([], include_deleted=include_deleted)

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
            with self._commit_or_flush(session) as using_internal_session:
                session.add(instance)
            if using_internal_session:
                session.refresh(instance)
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
            with self._commit_or_flush(session) as using_internal_session:
                session.add_all(instances)
            if using_internal_session:
                for instance in instances:
                    session.refresh(instance)

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
            with self._commit_or_flush(session) as using_internal_session:
                session.add_all(instances)
            if using_internal_session:
                for instance in instances:
                    session.refresh(instance)
        return instances

    def bulk_update(
        self,
        values: Sequence[dict],
        *,
        filter_by: dict | None = None,
        filters: Sequence[ColumnElement] | None = None,
        allow_unfiltered: bool = False,
        include_deleted: bool = False,
    ) -> int:
        """複数レコードを一括更新し、影響行数を返す。

        ``filter_by`` 未指定時は各 dict の ``id`` を条件として使います。
        ``filter_by`` 指定時は渡された条件に対して各 dict の値を適用します。
        ``filter_by`` に空の dict を渡すと全件が対象になるため、
        ``allow_unfiltered=True`` を明示しない限り ``ValueError`` を送出します。
        ``include_deleted=True`` を指定すると、論理削除済みの行も更新対象にします。

        ``filters`` と ``filter_by`` は AND で結合されます。``filter_by`` を指定せずに
        ``filters`` を指定した場合、各 values 辞書の更新内容は条件に一致する行に適用されます。
        """
        if not values:
            return 0

        if filter_by is None and not filters:
            for row in values:
                if "id" not in row:
                    raise ValueError("bulk_update() requires each values dict to include 'id' when filter_by is not provided.")
        elif not filter_by and not filters and not allow_unfiltered:
            raise ValueError(
                "bulk_update() requires a non-empty filter_by or filters, or allow_unfiltered=True "
                "to update every matching row."
            )

        with self._session_scope() as session:
            rowcount = 0
            query_filters = [*(filters or []), *self._bulk_filters(filter_by)]
            self._append_soft_delete_filter(query_filters, include_deleted)
            with self._commit_or_flush(session):
                for row in values:
                    update_values = dict(row)
                    row_filters = list(query_filters)
                    if filter_by is None and "id" in update_values:
                        row_filters.append(self.model.id == update_values.pop("id"))
                    if not update_values:
                        continue

                    validate_values_no_nul_bytes(self.model, update_values)

                    result = session.execute(
                        update(self.model)
                        .where(and_(*row_filters) if row_filters else true())
                        .values(**update_values)
                        .execution_options(synchronize_session="fetch")
                    )
                    rowcount += result.rowcount or 0
            session.expire_all()
        return rowcount

    def bulk_delete(
        self,
        *,
        filter_by: dict | None = None,
        ids: Sequence[Any] | None = None,
        filters: Sequence[ColumnElement] | None = None,
        allow_unfiltered: bool = False,
    ) -> int:
        """条件に一致するレコードを一括削除し、影響行数を返す。

        SoftDeletableMixin 対応モデルでは ``deleted_at`` を更新し、非対応モデルでは
        物理削除します。``filter_by`` と ``ids`` を両方省略すると絞り込みが無くなる
        ため、``allow_unfiltered=True`` を明示しない限り ``ValueError`` を送出します。

        ``filters`` は ``filter_by`` および ``ids`` と AND で結合されます。
        """
        return self._bulk_delete(
            filter_by=filter_by,
            ids=ids,
            filters=filters,
            allow_unfiltered=allow_unfiltered,
            permanent=False,
        )

    def bulk_permanent_delete(
        self,
        *,
        filter_by: dict | None = None,
        ids: Sequence[Any] | None = None,
        filters: Sequence[ColumnElement] | None = None,
        allow_unfiltered: bool = False,
    ) -> int:
        """条件に一致するレコードを物理削除し、影響行数を返す。

        ``filters`` と ``filter_by`` / ``ids`` は AND で結合します。全て省略すると
        絞り込みが無くなるため、``allow_unfiltered=True`` を明示しない限り
        ``ValueError`` を送出します。
        """
        return self._bulk_delete(
            filter_by=filter_by,
            ids=ids,
            filters=filters,
            allow_unfiltered=allow_unfiltered,
            permanent=True,
        )

    def _bulk_delete(
        self,
        *,
        filter_by: dict | None,
        ids: Sequence[Any] | None,
        filters: Sequence[ColumnElement] | None,
        allow_unfiltered: bool,
        permanent: bool,
    ) -> int:
        query_filters = [*(filters or []), *self._bulk_filters(filter_by)]
        if ids is not None:
            if not ids:
                return 0
            query_filters.append(self._resolve_ids_filter(ids))

        if not query_filters and not allow_unfiltered:
            raise ValueError(
                "bulk_delete() requires filters, filter_by, or ids, or allow_unfiltered=True "
                "to delete every row."
            )

        with self._session_scope() as session:
            rowcount = 0
            with self._commit_or_flush(session):
                if self._has_soft_delete() and not permanent:
                    self._append_soft_delete_filter(query_filters)
                    statement = (
                        update(self.model)
                        .where(and_(*query_filters) if query_filters else true())
                        .values(deleted_at=datetime.now(timezone.utc))
                        .execution_options(synchronize_session="fetch")
                    )
                else:
                    statement = (
                        delete(self.model)
                        .where(and_(*query_filters) if query_filters else true())
                        .execution_options(synchronize_session="fetch")
                    )
                result = session.execute(statement)
                rowcount = result.rowcount or 0
            session.expire_all()
        return rowcount

    def get_or_create(self, lookup: dict, defaults: dict | None = None) -> tuple[T, bool]:
        """``lookup`` に一致する行を返し、存在しない場合は作成します。

        挿入は SAVEPOINT 内で実行されます。一意制約への同時挿入で別の処理が先行した場合は、
        既存の行を検索して返します。
        """
        if not lookup:
            raise ValueError("get_or_create() requires a non-empty lookup.")

        with self._session_scope() as session:
            with self._commit_or_flush(session):
                existing = self._get_by_lookup_in_session(session, lookup)
                if existing is not None:
                    return existing, False

                instance = self.model(**(dict(defaults or {}) | lookup))
                self._ensure_savepoint_transaction(session)
                try:
                    with session.begin_nested():
                        session.add(instance)
                        session.flush()
                except IntegrityError as exc:
                    if not is_unique_violation(exc):
                        raise
                    existing = self._get_by_lookup_in_session(session, lookup)
                    if existing is None:
                        raise
                    return existing, False

                return instance, True

    @staticmethod
    def _ensure_savepoint_transaction(session) -> None:
        connection = session.connection()
        if connection.dialect.name == "sqlite":
            # Legacy SQLite transaction control does not begin a database
            # transaction for SELECT; a root SAVEPOINT would commit on release.
            driver_connection = connection.connection.driver_connection
            if not driver_connection.in_transaction:
                connection.exec_driver_sql("BEGIN")

    def _get_by_lookup_in_session(self, session: Session, lookup: dict) -> Optional[T]:
        filters = [
            self._resolve_equality_filter(column_name, value)
            for column_name, value in lookup.items()
        ]
        self._append_soft_delete_filter(filters)
        query = select(self.model).where(and_(*filters)).limit(1)
        return session.execute(query).scalars().first()

    def remove(self, instance: T) -> None:
        """
        インスタンスを削除

        Args:
            instance (T): 削除するインスタンス
        """
        with self._session_scope() as session:
            with self._commit_or_flush(session):
                managed_instance = session.merge(instance)
                session.delete(managed_instance)

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
                - options (list | tuple | Load): SQLAlchemy クエリオプション（eager loading等）

        Returns:
            List[T]: モデルのリスト。

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
            >>> items = repo.find(
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

        base_filters = [*(filters or []), *self._build_filters(params)]
        return self._find_with_filters(base_filters, include_deleted=include_deleted, **kwargs)

    def _find_with_filters(
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
        return self._execute_scalars_unique(query)

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

    def count(
        self,
        filters: Optional[List[Callable]] = None,
        include_deleted: bool = False,
        params: Optional[FilterParams] = None,
    ) -> int:
        """
        指定したフィルタ条件に一致するレコード数を返す

        Args:
            filters (Optional[List[Callable]]): フィルタ条件のリスト。
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
            params (Optional[FilterParams]): フィルタ条件に AND で追加する検索パラメータ。

        Returns:
            int: 一致するレコード数
        """
        query = select(func.count()).select_from(self.model)
        all_filters = [*(filters or []), *self._build_filters(params)]
        self._append_soft_delete_filter(all_filters, include_deleted)

        if all_filters:
            query = query.where(and_(*all_filters))
        with self._session_scope() as session:
            return session.execute(query).scalar()

    def count_by_params(self, params: Optional[FilterParams] = None, include_deleted: bool = False) -> int:
        return self.count(params=params, include_deleted=include_deleted)

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
        filters = [self._resolve_ids_filter(ids)]
        return self._find_with_filters(filters, include_deleted=include_deleted, **kwargs)
