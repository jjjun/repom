from datetime import datetime
from typing import Callable, Generic, List, Optional, TypeVar

from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError

import logging

T = TypeVar('T')

# Logger
logger = logging.getLogger(__name__)


class SoftDeleteRepositoryMixin(Generic[T]):
    """論理削除機能を提供する同期版リポジトリ Mixin.

    BaseRepository と組み合わせて使用します。
    """

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

        with self._session_scope() as session:
            item = self.get_by_id(id, include_deleted=False)
            if not item:
                return False

            item.soft_delete()
            try:
                session.commit()
                return True
            except SQLAlchemyError:
                session.rollback()
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

        with self._session_scope() as session:
            item = self.get_by_id(id, include_deleted=True)
            if not item or not item.is_deleted:
                return False

            item.restore()
            try:
                session.commit()
                return True
            except SQLAlchemyError:
                session.rollback()
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

        with self._session_scope() as session:
            try:
                session.delete(item)
                session.commit()
                logger.warning(
                    f"Permanently deleted: {self.model.__name__} id={id}"
                )
                return True
            except SQLAlchemyError:
                session.rollback()
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
        with self._session_scope() as session:
            return session.execute(query).scalars().all()

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
        with self._session_scope() as session:
            return session.execute(query).scalars().all()


class AsyncSoftDeleteRepositoryMixin(Generic[T]):
    """論理削除機能を提供する非同期版リポジトリ Mixin.

    AsyncBaseRepository と組み合わせて使用します。
    """

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

        async with self._session_scope() as session:
            item = await self.get_by_id(id, include_deleted=False)
            if not item:
                return False

            item.soft_delete()
            try:
                await session.commit()
                return True
            except SQLAlchemyError:
                await session.rollback()
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

        async with self._session_scope() as session:
            item = await self.get_by_id(id, include_deleted=True)
            if not item or not item.is_deleted:
                return False

            item.restore()
            try:
                await session.commit()
                return True
            except SQLAlchemyError:
                await session.rollback()
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

        async with self._session_scope() as session:
            try:
                await session.delete(item)
                await session.commit()
                logger.warning(
                    f"Permanently deleted: {self.model.__name__} id={id}"
                )
                return True
            except SQLAlchemyError:
                await session.rollback()
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
        async with self._session_scope() as session:
            result = await session.execute(query)
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
        async with self._session_scope() as session:
            result = await session.execute(query)
            return result.scalars().all()
