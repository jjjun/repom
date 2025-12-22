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
from sqlalchemy import ColumnElement, UnaryExpression, and_, select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging

# FilterParams is imported from base_repository
from repom.base_repository import FilterParams

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class AsyncBaseRepository(Generic[T]):
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
        return hasattr(self.model, 'deleted_at')

    async def get_by(
        self,
        column_name: str,
        value: Any,
        *extra_filters: ColumnElement,
        single: bool = False,
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

        Returns:
            Union[List[T], Optional[T]]: レコードのリストまたは単一レコード

        Raises:
            AttributeError: 指定されたカラムがモデルに存在しない場合
        """
        if not hasattr(self.model, column_name):
            raise AttributeError(f"Column '{column_name}' does not exist on {self.model.__name__}")

        column = getattr(self.model, column_name)
        filters = [column == value, *extra_filters]
        if single:
            return await self.find_one(filters=filters)
        return await self.find(filters=filters)

    async def get_by_id(self, id: int, include_deleted: bool = False) -> Optional[T]:
        """指定されたIDのインスタンスを取得

        Args:
            id (int): インスタンスのID
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone
        """
        extra_filters = []
        if self._has_soft_delete() and not include_deleted:
            extra_filters.append(self.model.deleted_at.is_(None))

        return await self.get_by('id', id, *extra_filters, single=True)

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
            T: 保存したインスタンス
        """
        try:
            self.session.add(instance)
            await self.session.commit()
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
        """
        try:
            self.session.add_all(instances)
            await self.session.commit()
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
        """クエリにオプションを設定するメソッド

        このメソッドは、クエリに対して offset、limit、order_by、および options を設定します。
        デフォルトでは、order_by はモデルの id フィールドの昇順に設定されます。

        Args:
            query: SQLAlchemy のクエリオブジェクト
            **kwargs: 任意のキーワード引数。以下の引数をサポートします。
                - offset (int): 取得するデータの開始位置
                - limit (int): 取得するデータの件数
                - order_by (Callable | str): 結果を並べ替えるための指定
                - options (list | Load): SQLAlchemy の load options (joinedload, selectinload など)

        Returns:
            クエリオブジェクトにオプションを設定したものを返します

        使用例:
            # Eager loading を使用して N+1 問題を解決
            from sqlalchemy.orm import joinedload, selectinload

            results = await repo.find(
                filters=[Model.status == 'active'],
                options=[joinedload(Model.user)]  # 関連モデルを eager load
            )

            # 複数の options を指定
            results = await repo.find(
                options=[
                    joinedload(Model.user),
                    selectinload(Model.tags)
                ]
            )
        """
        offset = kwargs.get('offset', None)
        limit = kwargs.get('limit', None)
        options = kwargs.get('options', None)
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
                order_by = self.parse_order_by(self.model, kwargs['order_by'])
            elif isinstance(kwargs['order_by'], (UnaryExpression, ColumnElement)):
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
        """order_by 文字列をパースして SQLAlchemy の order 式を返す

        フォーマット: "column_name:direction" (例: "created_at:desc", "id:asc")
        direction が指定されていない場合はデフォルトで "asc"

        カラム名は allowed_order_columns のホワイトリストに含まれている必要があります（セキュリティ対策）。
        サブクラスで allowed_order_columns を拡張できます。

        Args:
            model_class: SQLAlchemy モデルクラス
            order_by_str: ソート指定文字列 (例: "created_at:desc")

        Returns:
            SQLAlchemy カラム式 (asc() または desc())

        Raises:
            ValueError: カラムがホワイトリストにない、方向が無効、またはカラムが存在しない場合
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

    async def find_one(self, filters: list) -> Optional[T]:
        """指定されたフィルタ条件で単一レコードを取得

        Args:
            filters (list): フィルタ条件のリスト

        Returns:
            Optional[T]: インスタンスが見つかった場合はインスタンス、見つからない場合はNone
        """
        query = select(self.model).filter(*filters).limit(1)
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

    # ========================================
    # 論理削除関連メソッド
    # ========================================

    async def soft_delete(self, id: int) -> bool:
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
            repo = AsyncBaseRepository(MyModel, session)
            if await repo.soft_delete(1):
                print("削除成功")
        """
        if not self._has_soft_delete():
            raise ValueError(
                f"{self.model.__name__} does not support soft delete. "
                "Add SoftDeletableMixin to the model."
            )

        item = await self.get_by_id(id, include_deleted=False)
        if not item:
            return False

        item.soft_delete()
        try:
            await self.session.commit()
            return True
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def restore(self, id: int) -> bool:
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
            repo = AsyncBaseRepository(MyModel, session)
            if await repo.restore(1):
                print("復元成功")
        """
        if not self._has_soft_delete():
            raise ValueError(
                f"{self.model.__name__} does not support soft delete."
            )

        item = await self.get_by_id(id, include_deleted=True)
        if not item or not item.is_deleted:
            return False

        item.restore()
        try:
            await self.session.commit()
            return True
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def permanent_delete(self, id: int) -> bool:
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
            repo = AsyncBaseRepository(MyModel, session)
            if await repo.permanent_delete(1):
                print("物理削除成功")
        """
        # 削除済みレコードも含めて取得
        if self._has_soft_delete():
            item = await self.get_by_id(id, include_deleted=True)
        else:
            item = await self.get_by_id(id)

        if not item:
            return False

        try:
            await self.session.delete(item)
            await self.session.commit()
            logger.warning(
                f"Permanently deleted: {self.model.__name__} id={id}"
            )
            return True
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def find_deleted(self, filters: Optional[List[Callable]] = None, **kwargs) -> List[T]:
        """削除済みレコードのみ取得

        deleted_at が設定されているレコードのみを検索します。
        バッチ処理などで削除済みデータを検索する際に使用します。

        Args:
            filters (Optional[List[Callable]]): 追加のフィルタ条件
            **kwargs: offset, limit, order_by などのオプション

        Returns:
            List[T]: 削除済みレコードのリスト（論理削除非対応モデルは空リスト）

        使用例:
            repo = AsyncBaseRepository(MyModel, session)
            deleted_items = await repo.find_deleted()
        """
        if not self._has_soft_delete():
            return []

        all_filters = list(filters) if filters else []
        all_filters.append(self.model.deleted_at.isnot(None))

        query = select(self.model).where(and_(*all_filters))
        query = self.set_find_option(query, **kwargs)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def find_deleted_before(self, before_date: datetime, **kwargs) -> List[T]:
        """指定日時より前に削除されたレコードを取得

        Args:
            before_date (datetime): この日時より前に削除されたレコードを検索
            **kwargs: offset, limit, order_by などのオプション

        Returns:
            List[T]: 条件に一致するレコードのリスト（論理削除非対応モデルは空リスト）

        使用例:
            from datetime import datetime, timedelta, timezone

            # 30日以上前に削除されたレコードを取得
            repo = AsyncBaseRepository(MyModel, session)
            threshold = datetime.now(timezone.utc) - timedelta(days=30)
            old_deleted = await repo.find_deleted_before(threshold)

            # 物理削除
            for item in old_deleted:
                await repo.permanent_delete(item.id)
        """
        if not self._has_soft_delete():
            return []

        filters = [
            self.model.deleted_at.isnot(None),
            self.model.deleted_at < before_date
        ]

        query = select(self.model).where(and_(*filters))
        query = self.set_find_option(query, **kwargs)
        result = await self.session.execute(query)
        return result.scalars().all()
