"""repom.testing のフィクスチャエンジン設定のテスト (repom#166)

create_test_fixtures / create_async_test_fixtures が DatabaseManager と同じ
config.engine_kwargs_for_url / DatabaseManager.resolve_engine_settings を使って
PostgreSQL 用の URL・engine kwargs を正しく導出することを検証する。
create_engine / create_async_engine をパッチし、実際の PostgreSQL 接続は行わない。
"""

import pytest
from sqlalchemy import Integer, create_engine, select
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.pool import StaticPool
import sqlalchemy.ext.asyncio as sa_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

import repom.database as database_module
import repom.testing as testing_module
from repom.config import config
from repom.database import DatabaseManager, convert_to_async_uri as database_convert_to_async_uri
from repom.models.base_model import BaseModel
from repom.testing import create_async_test_fixtures, create_test_fixtures


class _StopAfterCapture(Exception):
    """create_engine / create_async_engine に渡された引数を捕捉した直後に

    フィクスチャの実行を打ち切るためだけの例外。実際の DB 接続や
    Base.metadata.create_all を発生させずに、渡された URL/kwargs だけを検証する。
    """


class GlobalManagerFixtureModel(BaseModel):
    __tablename__ = 'global_manager_fixture_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class TestCreateAsyncTestFixturesPostgresSettings:
    """create_async_test_fixtures の async_db_engine が asyncpg 用の

    URL・connect_args を組み立てることを確認する（psycopg の connect_args を
    そのまま渡すと connect() が TypeError になる repom#166 の回帰防止）。
    """

    @pytest.mark.asyncio
    async def test_async_db_engine_builds_asyncpg_url_and_connect_args(self, monkeypatch):
        captured = {}

        def fake_create_async_engine(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            raise _StopAfterCapture

        monkeypatch.setattr(sa_asyncio, "create_async_engine", fake_create_async_engine)

        async_db_engine_fixture, _ = create_async_test_fixtures(
            db_url="postgresql+psycopg://u:p@h/db_test",
            model_loader=lambda: None,
            allow_destructive=True,
        )
        generator = async_db_engine_fixture.__wrapped__()
        with pytest.raises(_StopAfterCapture):
            await anext(generator)

        url = make_url(captured["url"])
        assert url.drivername == "postgresql+asyncpg"
        assert "sslmode" not in url.query

        connect_args = captured["kwargs"]["connect_args"]
        assert connect_args["timeout"] == config.db_connect_timeout
        assert connect_args["server_settings"] == {
            "application_name": config.db_application_name
        }
        assert "connect_timeout" not in connect_args
        assert "check_same_thread" not in connect_args


class TestCreateTestFixturesPostgresUnderSqliteConfig:
    """config.db_type が sqlite のままでも、フィクスチャ URL が PostgreSQL

    なら PostgreSQL 用の engine kwargs が使われることを確認する
    （config.db_type ではなくフィクスチャ URL のドライバーで判定するため）。
    """

    def test_db_engine_passes_postgres_kwargs_without_check_same_thread(self, monkeypatch):
        monkeypatch.setattr(config, "db_type", "sqlite")
        captured = {}

        def fake_create_engine(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            raise _StopAfterCapture

        monkeypatch.setattr(testing_module, "create_engine", fake_create_engine)

        db_engine_fixture, _ = create_test_fixtures(
            db_url="postgresql+psycopg://u:p@h/db_test",
            model_loader=lambda: None,
            allow_destructive=True,
        )
        generator = db_engine_fixture.__wrapped__()
        with pytest.raises(_StopAfterCapture):
            next(generator)

        assert captured["url"] == "postgresql+psycopg://u:p@h/db_test"
        kwargs = captured["kwargs"]
        assert kwargs["pool_size"] == config.db_pool_size
        assert kwargs["max_overflow"] == config.db_max_overflow
        assert kwargs["connect_args"] == {
            "connect_timeout": config.db_connect_timeout,
            "application_name": config.db_application_name,
        }


class TestConvertToAsyncUriReExport:
    """repom.testing.convert_to_async_uri が repom.database.convert_to_async_uri の

    別名（同一オブジェクト）であることを確認する（repom#166 の重複実装解消）。
    """

    def test_is_same_function_object_as_database_module(self):
        assert testing_module.convert_to_async_uri is database_convert_to_async_uri

    def test_converts_psycopg_url_to_asyncpg(self):
        result = testing_module.convert_to_async_uri("postgresql+psycopg://u:p@h/db")
        assert result == "postgresql+asyncpg://u:p@h/db"


def test_db_engine_passes_sqlite_memory_kwargs(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        raise _StopAfterCapture

    monkeypatch.setattr(testing_module, "create_engine", fake_create_engine)

    db_engine_fixture, _ = create_test_fixtures(
        db_url="sqlite:///:memory:",
        model_loader=lambda: None,
        allow_destructive=True,
    )
    generator = db_engine_fixture.__wrapped__()
    with pytest.raises(_StopAfterCapture):
        next(generator)

    assert captured["url"] == "sqlite:///:memory:"
    assert captured["kwargs"]["connect_args"] == {"check_same_thread": False}
    assert captured["kwargs"]["poolclass"] is StaticPool


def test_sync_test_fixture_binds_global_manager_for_reusable_transactions(monkeypatch):
    manager = DatabaseManager()
    previous_engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(database_module, "_db_manager", manager)
    monkeypatch.setattr(testing_module, "_db_manager", manager)
    db_engine_fixture, _ = create_test_fixtures(
        db_url="sqlite:///:memory:",
        model_loader=lambda: None,
        bind_global_manager=True,
    )

    with manager.bind_engine_for_tests(previous_engine):
        generator = db_engine_fixture.__wrapped__()
        fixture_engine = next(generator)
        try:
            assert database_module.get_sync_engine() is fixture_engine
            with database_module.get_reusable_sync_transaction() as session:
                assert session.execute(select(GlobalManagerFixtureModel)).all() == []
        finally:
            with pytest.raises(StopIteration):
                next(generator)

        assert database_module.get_sync_engine() is previous_engine

    previous_engine.dispose()


@pytest.mark.asyncio
async def test_async_test_fixture_binds_global_manager_for_reusable_transactions(monkeypatch):
    manager = DatabaseManager()
    previous_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database_module, "_db_manager", manager)
    monkeypatch.setattr(testing_module, "_db_manager", manager)
    async_db_engine_fixture, _ = create_async_test_fixtures(
        db_url="sqlite:///:memory:",
        model_loader=lambda: None,
        bind_global_manager=True,
    )

    with manager.bind_engine_for_tests(previous_engine):
        generator = async_db_engine_fixture.__wrapped__()
        fixture_engine = await anext(generator)
        try:
            assert await database_module.get_async_engine() is fixture_engine
            async with database_module.get_reusable_async_transaction() as session:
                result = await session.execute(select(GlobalManagerFixtureModel))
                assert result.all() == []
        finally:
            with pytest.raises(StopAsyncIteration):
                await anext(generator)

        assert await database_module.get_async_engine() is previous_engine

    await previous_engine.dispose()
