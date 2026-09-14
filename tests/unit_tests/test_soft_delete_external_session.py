"""
論理削除系メソッド（soft_delete / restore / permanent_delete）の
外部セッション使用時の commit/rollback 動作テスト (repom#136)

save/saves/remove について tests/unit_tests/test_external_session_commit.py で
確立された「外部セッションでは commit も rollback も呼び出し元に委ねる」契約が、
論理削除系メソッドにも同様に適用されることを検証します。
"""

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import String, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

from repom.database import get_async_db_transaction, get_reusable_sync_transaction
from repom.mixins import SoftDeletableMixin
from repom.models.base_model import BaseModel
from repom.repositories import AsyncBaseRepository, BaseRepository


class ExternalSessionSoftDeleteModel(BaseModel, SoftDeletableMixin):
    """テスト用モデル（論理削除対応）"""
    __tablename__ = "test_external_session_soft_delete"

    name: Mapped[str] = mapped_column(String(100))


class ExternalSessionSoftDeleteRepository(BaseRepository[ExternalSessionSoftDeleteModel]):
    """テスト用リポジトリ（同期）"""

    def __init__(self, session=None):
        super().__init__(ExternalSessionSoftDeleteModel, session)


class AsyncExternalSessionSoftDeleteRepository(AsyncBaseRepository[ExternalSessionSoftDeleteModel]):
    """テスト用リポジトリ（非同期）"""

    def __init__(self, session=None):
        super().__init__(ExternalSessionSoftDeleteModel, session)


# get_async_db_transaction() は FastAPI Depends 互換のため async generator の
# まま公開されている（tests/unit_tests/test_async_database.py 参照）。ここでは
# get_reusable_sync_transaction() と同じ感覚で `async with` を使えるよう、
# テスト内だけで asynccontextmanager を被せる。
_external_async_transaction = asynccontextmanager(get_async_db_transaction)


# ---------------------------------------------------------------------------
# does_not_commit_external_session: 外部セッションでは commit しない
# ---------------------------------------------------------------------------


def test_soft_delete_does_not_commit_external_session(db_test):
    """外部セッション: soft_delete() が commit を実行しない"""
    prep_repo = ExternalSessionSoftDeleteRepository()
    item = prep_repo.save(ExternalSessionSoftDeleteModel(name="soft_delete_external_target"))
    item_id = item.id

    with get_reusable_sync_transaction() as session:
        repo = ExternalSessionSoftDeleteRepository(session)

        assert repo.soft_delete(item_id) is True

        # 同じトランザクション内では反映されている
        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.id == item_id
        )
        found = session.execute(stmt).scalar_one()
        assert found.is_deleted is True

    # with ブロックを抜けた後（呼び出し元が commit した後）、別のセッションでも見える
    verify_repo = ExternalSessionSoftDeleteRepository()
    assert verify_repo.get_by_id(item_id) is None
    deleted_item = verify_repo.get_by_id(item_id, include_deleted=True)
    assert deleted_item is not None
    assert deleted_item.is_deleted is True


def test_restore_does_not_commit_external_session(db_test):
    """外部セッション: restore() が commit を実行しない"""
    prep_repo = ExternalSessionSoftDeleteRepository()
    item = prep_repo.save(ExternalSessionSoftDeleteModel(name="restore_external_target"))
    item_id = item.id
    assert prep_repo.soft_delete(item_id) is True

    with get_reusable_sync_transaction() as session:
        repo = ExternalSessionSoftDeleteRepository(session)

        assert repo.restore(item_id) is True

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.id == item_id
        )
        found = session.execute(stmt).scalar_one()
        assert found.is_deleted is False

    verify_repo = ExternalSessionSoftDeleteRepository()
    restored_item = verify_repo.get_by_id(item_id)
    assert restored_item is not None
    assert restored_item.is_deleted is False


def test_permanent_delete_does_not_commit_external_session(db_test):
    """外部セッション: permanent_delete() が commit を実行しない"""
    prep_repo = ExternalSessionSoftDeleteRepository()
    item = prep_repo.save(ExternalSessionSoftDeleteModel(name="permanent_delete_external_target"))
    item_id = item.id

    with get_reusable_sync_transaction() as session:
        repo = ExternalSessionSoftDeleteRepository(session)

        assert repo.permanent_delete(item_id) is True

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.id == item_id
        )
        found = session.execute(stmt).scalar_one_or_none()
        assert found is None

    verify_repo = ExternalSessionSoftDeleteRepository()
    assert verify_repo.get_by_id(item_id, include_deleted=True) is None


@pytest.mark.asyncio
async def test_async_soft_delete_does_not_commit_external_session():
    """外部セッション（非同期）: soft_delete() が commit を実行しない"""
    prep_repo = AsyncExternalSessionSoftDeleteRepository()
    item = await prep_repo.save(ExternalSessionSoftDeleteModel(name="async_soft_delete_external_target"))
    item_id = item.id

    async with _external_async_transaction() as session:
        repo = AsyncExternalSessionSoftDeleteRepository(session)

        assert await repo.soft_delete(item_id) is True

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.id == item_id
        )
        result = await session.execute(stmt)
        found = result.scalar_one()
        assert found.is_deleted is True

    verify_repo = AsyncExternalSessionSoftDeleteRepository()
    assert await verify_repo.get_by_id(item_id) is None
    deleted_item = await verify_repo.get_by_id(item_id, include_deleted=True)
    assert deleted_item is not None
    assert deleted_item.is_deleted is True


@pytest.mark.asyncio
async def test_async_restore_does_not_commit_external_session():
    """外部セッション（非同期）: restore() が commit を実行しない"""
    prep_repo = AsyncExternalSessionSoftDeleteRepository()
    item = await prep_repo.save(ExternalSessionSoftDeleteModel(name="async_restore_external_target"))
    item_id = item.id
    assert await prep_repo.soft_delete(item_id) is True

    async with _external_async_transaction() as session:
        repo = AsyncExternalSessionSoftDeleteRepository(session)

        assert await repo.restore(item_id) is True

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.id == item_id
        )
        result = await session.execute(stmt)
        found = result.scalar_one()
        assert found.is_deleted is False

    verify_repo = AsyncExternalSessionSoftDeleteRepository()
    restored_item = await verify_repo.get_by_id(item_id)
    assert restored_item is not None
    assert restored_item.is_deleted is False


@pytest.mark.asyncio
async def test_async_permanent_delete_does_not_commit_external_session():
    """外部セッション（非同期）: permanent_delete() が commit を実行しない"""
    prep_repo = AsyncExternalSessionSoftDeleteRepository()
    item = await prep_repo.save(ExternalSessionSoftDeleteModel(name="async_permanent_delete_external_target"))
    item_id = item.id

    async with _external_async_transaction() as session:
        repo = AsyncExternalSessionSoftDeleteRepository(session)

        assert await repo.permanent_delete(item_id) is True

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.id == item_id
        )
        result = await session.execute(stmt)
        found = result.scalar_one_or_none()
        assert found is None

    verify_repo = AsyncExternalSessionSoftDeleteRepository()
    assert await verify_repo.get_by_id(item_id, include_deleted=True) is None


# ---------------------------------------------------------------------------
# does_not_rollback_external_session: 外部セッションでは rollback しない
# （呼び出し元が保持する無関係な pending 変更を破棄しない）
# ---------------------------------------------------------------------------


def test_soft_delete_does_not_rollback_external_session(db_test, monkeypatch):
    """外部セッション: soft_delete() が失敗しても呼び出し元のセッションを
    rollback しない"""
    prep_repo = ExternalSessionSoftDeleteRepository()
    item = prep_repo.save(ExternalSessionSoftDeleteModel(name="soft_delete_rollback_guard_target"))
    item_id = item.id

    with get_reusable_sync_transaction() as session:
        repo = ExternalSessionSoftDeleteRepository(session)

        # 呼び出し元が保持する、soft_delete() とは無関係な pending 変更
        unrelated = ExternalSessionSoftDeleteModel(name="soft_delete_unrelated_pending")
        session.add(unrelated)
        session.flush()

        original_flush = session.flush

        def _boom(*args, **kwargs):
            raise SQLAlchemyError("forced failure inside soft_delete")

        monkeypatch.setattr(session, "flush", _boom)
        try:
            with pytest.raises(SQLAlchemyError):
                repo.soft_delete(item_id)
        finally:
            monkeypatch.setattr(session, "flush", original_flush)

        # rollback されていれば無関係な pending 変更も消えてしまう
        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.name == "soft_delete_unrelated_pending"
        )
        found = session.execute(stmt).scalar_one_or_none()
        assert found is not None


def test_restore_does_not_rollback_external_session(db_test, monkeypatch):
    """外部セッション: restore() が失敗しても呼び出し元のセッションを
    rollback しない"""
    prep_repo = ExternalSessionSoftDeleteRepository()
    item = prep_repo.save(ExternalSessionSoftDeleteModel(name="restore_rollback_guard_target"))
    item_id = item.id
    assert prep_repo.soft_delete(item_id) is True

    with get_reusable_sync_transaction() as session:
        repo = ExternalSessionSoftDeleteRepository(session)

        unrelated = ExternalSessionSoftDeleteModel(name="restore_unrelated_pending")
        session.add(unrelated)
        session.flush()

        original_flush = session.flush

        def _boom(*args, **kwargs):
            raise SQLAlchemyError("forced failure inside restore")

        monkeypatch.setattr(session, "flush", _boom)
        try:
            with pytest.raises(SQLAlchemyError):
                repo.restore(item_id)
        finally:
            monkeypatch.setattr(session, "flush", original_flush)

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.name == "restore_unrelated_pending"
        )
        found = session.execute(stmt).scalar_one_or_none()
        assert found is not None


def test_permanent_delete_does_not_rollback_external_session(db_test, monkeypatch):
    """外部セッション: permanent_delete() が失敗しても呼び出し元のセッションを
    rollback しない"""
    prep_repo = ExternalSessionSoftDeleteRepository()
    item = prep_repo.save(ExternalSessionSoftDeleteModel(name="permanent_delete_rollback_guard_target"))
    item_id = item.id

    with get_reusable_sync_transaction() as session:
        repo = ExternalSessionSoftDeleteRepository(session)

        unrelated = ExternalSessionSoftDeleteModel(name="permanent_delete_unrelated_pending")
        session.add(unrelated)
        session.flush()

        original_flush = session.flush

        def _boom(*args, **kwargs):
            raise SQLAlchemyError("forced failure inside permanent_delete")

        monkeypatch.setattr(session, "flush", _boom)
        try:
            with pytest.raises(SQLAlchemyError):
                repo.permanent_delete(item_id)
        finally:
            monkeypatch.setattr(session, "flush", original_flush)

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.name == "permanent_delete_unrelated_pending"
        )
        found = session.execute(stmt).scalar_one_or_none()
        assert found is not None


@pytest.mark.asyncio
async def test_async_soft_delete_does_not_rollback_external_session(monkeypatch):
    """外部セッション（非同期）: soft_delete() が失敗しても呼び出し元のセッションを
    rollback しない"""
    prep_repo = AsyncExternalSessionSoftDeleteRepository()
    item = await prep_repo.save(
        ExternalSessionSoftDeleteModel(name="async_soft_delete_rollback_guard_target")
    )
    item_id = item.id

    async with _external_async_transaction() as session:
        repo = AsyncExternalSessionSoftDeleteRepository(session)

        unrelated = ExternalSessionSoftDeleteModel(name="async_soft_delete_unrelated_pending")
        session.add(unrelated)
        await session.flush()

        original_flush = session.flush

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("forced failure inside async soft_delete")

        monkeypatch.setattr(session, "flush", _boom)
        try:
            with pytest.raises(SQLAlchemyError):
                await repo.soft_delete(item_id)
        finally:
            monkeypatch.setattr(session, "flush", original_flush)

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.name == "async_soft_delete_unrelated_pending"
        )
        result = await session.execute(stmt)
        found = result.scalar_one_or_none()
        assert found is not None


@pytest.mark.asyncio
async def test_async_restore_does_not_rollback_external_session(monkeypatch):
    """外部セッション（非同期）: restore() が失敗しても呼び出し元のセッションを
    rollback しない"""
    prep_repo = AsyncExternalSessionSoftDeleteRepository()
    item = await prep_repo.save(
        ExternalSessionSoftDeleteModel(name="async_restore_rollback_guard_target")
    )
    item_id = item.id
    assert await prep_repo.soft_delete(item_id) is True

    async with _external_async_transaction() as session:
        repo = AsyncExternalSessionSoftDeleteRepository(session)

        unrelated = ExternalSessionSoftDeleteModel(name="async_restore_unrelated_pending")
        session.add(unrelated)
        await session.flush()

        original_flush = session.flush

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("forced failure inside async restore")

        monkeypatch.setattr(session, "flush", _boom)
        try:
            with pytest.raises(SQLAlchemyError):
                await repo.restore(item_id)
        finally:
            monkeypatch.setattr(session, "flush", original_flush)

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.name == "async_restore_unrelated_pending"
        )
        result = await session.execute(stmt)
        found = result.scalar_one_or_none()
        assert found is not None


@pytest.mark.asyncio
async def test_async_permanent_delete_does_not_rollback_external_session(monkeypatch):
    """外部セッション（非同期）: permanent_delete() が失敗しても呼び出し元の
    セッションを rollback しない"""
    prep_repo = AsyncExternalSessionSoftDeleteRepository()
    item = await prep_repo.save(
        ExternalSessionSoftDeleteModel(name="async_permanent_delete_rollback_guard_target")
    )
    item_id = item.id

    async with _external_async_transaction() as session:
        repo = AsyncExternalSessionSoftDeleteRepository(session)

        unrelated = ExternalSessionSoftDeleteModel(name="async_permanent_delete_unrelated_pending")
        session.add(unrelated)
        await session.flush()

        original_flush = session.flush

        async def _boom(*args, **kwargs):
            raise SQLAlchemyError("forced failure inside async permanent_delete")

        monkeypatch.setattr(session, "flush", _boom)
        try:
            with pytest.raises(SQLAlchemyError):
                await repo.permanent_delete(item_id)
        finally:
            monkeypatch.setattr(session, "flush", original_flush)

        stmt = select(ExternalSessionSoftDeleteModel).where(
            ExternalSessionSoftDeleteModel.name == "async_permanent_delete_unrelated_pending"
        )
        result = await session.execute(stmt)
        found = result.scalar_one_or_none()
        assert found is not None
