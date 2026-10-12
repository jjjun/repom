from sqlalchemy import Integer, String, event, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Session, mapped_column

import pytest

from repom import AsyncBaseRepository, BaseRepository
from repom.models.base_model import BaseModel
from repom.repositories import async_base_repository as async_base_repository_module
from repom.repositories import base_repository as base_repository_module


class ProtectedApiModel(BaseModel):
    __tablename__ = "test_repository_protected_api"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class SyncProtectedApiRepository(BaseRepository[ProtectedApiModel]):
    def find_by_name(self, name: str) -> ProtectedApiModel | None:
        with self._session_scope() as session:
            query = self._base_select().where(ProtectedApiModel.name == name)
            return session.execute(query).scalars().first()

    def create(self, name: str) -> ProtectedApiModel:
        entry = ProtectedApiModel(name=name)
        with self._session_scope() as session:
            with self._commit_or_flush(session) as using_internal_session:
                session.add(entry)
            if using_internal_session:
                session.refresh(entry)
        return entry


class AsyncProtectedApiRepository(AsyncBaseRepository[ProtectedApiModel]):
    async def find_by_name(self, name: str) -> ProtectedApiModel | None:
        async with self._session_scope() as session:
            query = self._base_select().where(ProtectedApiModel.name == name)
            result = await session.execute(query)
            return result.scalars().first()

    async def create(self, name: str) -> ProtectedApiModel:
        entry = ProtectedApiModel(name=name)
        async with self._session_scope() as session:
            async with self._commit_or_flush(session) as using_internal_session:
                session.add(entry)
            if using_internal_session:
                await session.refresh(entry)
        return entry


def test_sync_protected_api_uses_external_session_without_committing(db_test):
    session = db_test()
    repo = SyncProtectedApiRepository(ProtectedApiModel, session=session)

    entry = repo.create("sync-external")

    assert repo.find_by_name(entry.name) is entry
    transaction = session.get_transaction()
    assert transaction is not None and transaction.is_active

    session.rollback()

    query = select(ProtectedApiModel).where(ProtectedApiModel.id == entry.id)
    assert session.execute(query).scalar_one_or_none() is None


def test_sync_protected_api_commits_and_detaches_internal_session(db_test, monkeypatch):
    sessions = []
    commits = []

    def get_internal_session():
        session = Session(bind=db_test.connection())
        sessions.append(session)
        event.listen(session, "before_commit", lambda current: commits.append(current))
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(base_repository_module, "get_db_session", get_internal_session)
    repo = SyncProtectedApiRepository(ProtectedApiModel)

    entry = repo.create("sync-internal")
    found = repo.find_by_name(entry.name)

    assert len(commits) == 1
    assert entry.id is not None
    assert sa_inspect(entry).detached
    assert found is not None and found.name == entry.name
    assert sa_inspect(found).detached
    assert len(sessions) == 2
    assert db_test().in_transaction()


@pytest.mark.asyncio
async def test_async_protected_api_uses_external_session_without_committing(async_db_test):
    repo = AsyncProtectedApiRepository(ProtectedApiModel, session=async_db_test)

    entry = await repo.create("async-external")

    assert await repo.find_by_name(entry.name) is entry
    assert async_db_test.in_transaction()

    await async_db_test.rollback()

    query = select(ProtectedApiModel).where(ProtectedApiModel.id == entry.id)
    result = await async_db_test.execute(query)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_async_protected_api_commits_and_detaches_internal_session(
    async_db_test, monkeypatch
):
    sessions = []
    commits = []

    async def get_internal_session():
        connection = await async_db_test.connection()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        sessions.append(session)
        event.listen(
            session.sync_session,
            "before_commit",
            lambda current: commits.append(current),
        )
        try:
            yield session
        finally:
            await session.close()

    monkeypatch.setattr(async_base_repository_module, "get_async_db_session", get_internal_session)
    repo = AsyncProtectedApiRepository(ProtectedApiModel)

    entry = await repo.create("async-internal")
    found = await repo.find_by_name(entry.name)

    assert len(commits) == 1
    assert entry.id is not None
    assert sa_inspect(entry).detached
    assert found is not None and found.name == entry.name
    assert sa_inspect(found).detached
    assert len(sessions) == 2
    assert async_db_test.in_transaction()
