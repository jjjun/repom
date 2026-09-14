"""
_session_scope() のスレッド/タスク分離テスト (repom#134)

session= を省略したリポジトリインスタンスを複数の task/thread で共有した場合、
内部で開くセッションが取り合われないこと（他の呼び出し元のセッション・
未コミットの変更・identity map を参照しないこと）を検証する。
"""
import asyncio
import itertools
import threading

import pytest
import pytest_asyncio
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from repom import AsyncBaseRepository, BaseRepository
from repom.models.base_model import BaseModel
from repom.repositories import async_base_repository as async_base_repository_module
from repom.repositories import base_repository as base_repository_module


class SessionIsolationModel(BaseModel):
    """このテストファイル専用のモデル"""

    __tablename__ = "test_session_isolation"

    name: Mapped[str] = mapped_column(String(100))


# ---------------------------------------------------------------------------
# 純粋なオブジェクト同一性の検証用フェイクセッション
# ---------------------------------------------------------------------------
# get_db_session() / get_async_db_session() を差し替え、呼び出しごとに
# 新しいセッションオブジェクトを返す。実 DB には触れない。

_fake_session_counter = itertools.count(1)


class _FakeSession:
    def __init__(self):
        self.seq = next(_fake_session_counter)

    def expunge_all(self):
        pass


def _fake_get_db_session():
    session = _FakeSession()
    try:
        yield session
    finally:
        pass


async def _fake_get_async_db_session():
    session = _FakeSession()
    try:
        yield session
    finally:
        pass


@pytest.mark.asyncio
async def test_async_repository_does_not_share_session_across_tasks(monkeypatch):
    """1つのリポジトリインスタンスを2つの asyncio task が使っても、
    内部セッションが取り合われないこと。"""
    monkeypatch.setattr(async_base_repository_module, "get_async_db_session", _fake_get_async_db_session)
    repo = AsyncBaseRepository(model=SessionIsolationModel)

    scope_opened = asyncio.Event()
    release_holder = asyncio.Event()
    observed = {}

    async def holder():
        async with repo._session_scope() as session:
            observed["A"] = session
            scope_opened.set()
            await release_holder.wait()

    async def reader():
        await scope_opened.wait()
        async with repo._session_scope() as session:
            observed["B"] = session
        release_holder.set()

    await asyncio.gather(holder(), reader())

    assert observed["A"] is not observed["B"]


def test_sync_repository_does_not_share_session_across_threads(monkeypatch):
    """1つのリポジトリインスタンスを2つのスレッドが使っても、
    内部セッションが取り合われないこと。"""
    monkeypatch.setattr(base_repository_module, "get_db_session", _fake_get_db_session)
    repo = BaseRepository(model=SessionIsolationModel)

    scope_opened = threading.Event()
    release_holder = threading.Event()
    observed = {}

    def holder():
        with repo._session_scope() as session:
            observed["A"] = session
            scope_opened.set()
            release_holder.wait(timeout=5)

    def reader():
        scope_opened.wait(timeout=5)
        with repo._session_scope() as session:
            observed["B"] = session
        release_holder.set()

    holder_thread = threading.Thread(target=holder)
    reader_thread = threading.Thread(target=reader)
    holder_thread.start()
    reader_thread.start()
    holder_thread.join(timeout=5)
    reader_thread.join(timeout=5)

    assert observed["A"] is not observed["B"]


def test_explicit_session_still_honoured():
    """session= を明示した場合は従来通り、そのセッションがそのまま使われる。"""
    explicit_session = _FakeSession()
    repo = BaseRepository(model=SessionIsolationModel, session=explicit_session)

    assert repo.session is explicit_session

    with repo._session_scope() as session:
        assert session is explicit_session

    # スコープを抜けた後も明示的セッションはそのまま保持される
    assert repo.session is explicit_session


# ---------------------------------------------------------------------------
# 実 DB を使ったトランザクション分離 / identity map の検証
# ---------------------------------------------------------------------------
# :memory: + StaticPool では全セッションが同じ接続を共有してしまう
# （tests/unit_tests/test_database.py の TestSessionIsolation 参照）ため、
# ここではファイルベースの専用 engine を使い、実際に別コネクションで
# 動作することを保証する。


@pytest.fixture
def isolation_async_engine(tmp_path):
    db_path = tmp_path / "session_isolation_async.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    yield engine


@pytest.fixture
def isolation_async_sessionmaker(isolation_async_engine):
    return async_sessionmaker(bind=isolation_async_engine, class_=AsyncSession, expire_on_commit=False)


def _make_fake_get_async_db_session(sessionmaker):
    async def fake_get_async_db_session():
        session = sessionmaker()
        try:
            yield session
        finally:
            await session.close()

    return fake_get_async_db_session


@pytest_asyncio.fixture
async def isolation_table(isolation_async_engine):
    async with isolation_async_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all, tables=[SessionIsolationModel.__table__])
    yield
    async with isolation_async_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all, tables=[SessionIsolationModel.__table__])
    await isolation_async_engine.dispose()


@pytest.mark.asyncio
async def test_async_repository_isolates_uncommitted_writes(
    isolation_table, isolation_async_sessionmaker, monkeypatch
):
    """task A が commit せずに insert した行は、同じインスタンスを使う
    task B からは見えないこと。"""
    monkeypatch.setattr(
        async_base_repository_module,
        "get_async_db_session",
        _make_fake_get_async_db_session(isolation_async_sessionmaker),
    )
    repo = AsyncBaseRepository(model=SessionIsolationModel)

    task_a_ready = asyncio.Event()
    release_task_a = asyncio.Event()
    result = {}

    async def task_a():
        async with repo._session_scope() as session:
            session.add(SessionIsolationModel(id=1, name="from_a"))
            await session.flush()
            task_a_ready.set()
            await release_task_a.wait()
            # commit しない: task A のトランザクションは A のセッションにしか見えない

    async def task_b():
        await task_a_ready.wait()
        async with repo._session_scope() as session:
            result["seen_by_b"] = await session.get(SessionIsolationModel, 1)
        release_task_a.set()

    await asyncio.gather(task_a(), task_b())

    assert result["seen_by_b"] is None


@pytest.mark.asyncio
async def test_identity_map_not_shared_across_tasks(
    isolation_table, isolation_async_sessionmaker, monkeypatch
):
    """task A が読み込んでメモリ上だけで変更した値を、同じインスタンスを
    使う task B が DB の値として観測しないこと（identity map が
    共有されていないこと）。"""
    async with isolation_async_sessionmaker() as seed_session:
        seed_session.add(SessionIsolationModel(id=1, name="original"))
        await seed_session.commit()

    monkeypatch.setattr(
        async_base_repository_module,
        "get_async_db_session",
        _make_fake_get_async_db_session(isolation_async_sessionmaker),
    )
    repo = AsyncBaseRepository(model=SessionIsolationModel)

    task_a_ready = asyncio.Event()
    release_task_a = asyncio.Event()
    result = {}

    async def task_a():
        async with repo._session_scope() as session:
            obj = await session.get(SessionIsolationModel, 1)
            obj.name = "mutated_by_a"  # flush/commit しない: メモリ上だけの変更
            task_a_ready.set()
            await release_task_a.wait()

    async def task_b():
        await task_a_ready.wait()
        async with repo._session_scope() as session:
            obj = await session.get(SessionIsolationModel, 1)
            result["name_seen_by_b"] = obj.name
        release_task_a.set()

    await asyncio.gather(task_a(), task_b())

    assert result["name_seen_by_b"] == "original"
