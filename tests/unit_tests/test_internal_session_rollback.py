"""内部セッションの commit 失敗時に rollback されることのテスト (repom#161)

_commit_or_flush() ヘルパーへの集約後も、内部セッションで SQLAlchemyError
（IntegrityError）が発生した場合に rollback され、失敗した書き込みが残らず、
Repository インスタンス自体は以降も使用可能であることを検証する。
"""

import pytest
from sqlalchemy import String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel
from repom.repositories import AsyncBaseRepository, BaseRepository
from repom.repositories import async_base_repository as async_base_repository_module
from repom.repositories import base_repository as base_repository_module


class RollbackTestModel(BaseModel):
    """テスト用モデル（name にユニーク制約）"""
    __tablename__ = "test_internal_session_rollback"

    name: Mapped[str] = mapped_column(String(100), unique=True)


class RollbackTestRepository(BaseRepository[RollbackTestModel]):
    """テスト用リポジトリ（同期）"""

    def __init__(self, session=None):
        super().__init__(RollbackTestModel, session)


class AsyncRollbackTestRepository(AsyncBaseRepository[RollbackTestModel]):
    """テスト用リポジトリ（非同期）"""

    def __init__(self, session=None):
        super().__init__(RollbackTestModel, session)


def test_save_internal_session_rolls_back_on_integrity_error():
    """内部セッション: IntegrityError で commit が失敗したら rollback され、
    重複行が残らず、Repository は以降も使用可能であること"""
    repo = RollbackTestRepository()
    repo.save(RollbackTestModel(name="rollback_dup_target"))

    with pytest.raises(IntegrityError):
        repo.save(RollbackTestModel(name="rollback_dup_target"))

    verify_repo = RollbackTestRepository()
    matches = verify_repo.find(
        filters=[RollbackTestModel.name == "rollback_dup_target"], limit=10
    )
    assert len(matches) == 1

    # rollback 後も内部セッションを生成する Repository はそのまま使用できる
    saved = repo.save(RollbackTestModel(name="rollback_after_failure"))
    assert saved.id is not None


@pytest.mark.asyncio
async def test_async_save_internal_session_rolls_back_on_integrity_error():
    """内部セッション（非同期）: IntegrityError で commit が失敗したら rollback され、
    重複行が残らず、Repository は以降も使用可能であること"""
    repo = AsyncRollbackTestRepository()
    await repo.save(RollbackTestModel(name="async_rollback_dup_target"))

    with pytest.raises(IntegrityError):
        await repo.save(RollbackTestModel(name="async_rollback_dup_target"))

    verify_repo = AsyncRollbackTestRepository()
    matches = await verify_repo.find(
        filters=[RollbackTestModel.name == "async_rollback_dup_target"], limit=10
    )
    assert len(matches) == 1

    saved = await repo.save(RollbackTestModel(name="async_rollback_after_failure"))
    assert saved.id is not None


def test_permanent_delete_uses_a_single_internal_session(monkeypatch):
    """内部セッションの permanent_delete() は lookup と delete を1つの
    セッションで行う（従来は get_by_id() が別セッションを開いていた: repom#161）"""
    prep_repo = RollbackTestRepository()
    item = prep_repo.save(RollbackTestModel(name="permanent_delete_session_count_target"))
    item_id = item.id

    session_count = 0
    original_get_db_session = base_repository_module.get_db_session

    def counting_get_db_session():
        nonlocal session_count
        session_count += 1
        yield from original_get_db_session()

    monkeypatch.setattr(base_repository_module, "get_db_session", counting_get_db_session)

    repo = RollbackTestRepository()
    assert repo.permanent_delete(item_id) is True

    assert session_count == 1

    verify_repo = RollbackTestRepository()
    assert verify_repo.get_by_id(item_id) is None


@pytest.mark.asyncio
async def test_async_permanent_delete_uses_a_single_internal_session(monkeypatch):
    """内部セッション（非同期）の permanent_delete() は lookup と delete を
    1つのセッションで行う"""
    prep_repo = AsyncRollbackTestRepository()
    item = await prep_repo.save(
        RollbackTestModel(name="async_permanent_delete_session_count_target")
    )
    item_id = item.id

    session_count = 0
    original_get_async_db_session = async_base_repository_module.get_async_db_session

    async def counting_get_async_db_session():
        nonlocal session_count
        session_count += 1
        async for session in original_get_async_db_session():
            yield session

    monkeypatch.setattr(
        async_base_repository_module, "get_async_db_session", counting_get_async_db_session
    )

    repo = AsyncRollbackTestRepository()
    assert await repo.permanent_delete(item_id) is True

    assert session_count == 1

    verify_repo = AsyncRollbackTestRepository()
    assert await verify_repo.get_by_id(item_id) is None
