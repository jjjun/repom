"""repom.testing のフィクスチャエンジン設定のテスト (repom#166)

create_test_fixtures / create_async_test_fixtures が DatabaseManager と同じ
config.engine_kwargs_for_url / DatabaseManager.resolve_engine_settings を使って
PostgreSQL 用の URL・engine kwargs を正しく導出することを検証する。
create_engine / create_async_engine をパッチし、実際の PostgreSQL 接続は行わない。
"""

import pytest
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import StaticPool
import sqlalchemy.ext.asyncio as sa_asyncio

import repom.testing as testing_module
from repom.config import config
from repom.database import DatabaseManager
from repom.database import convert_to_async_uri as database_convert_to_async_uri
from repom.testing import create_async_test_fixtures, create_test_fixtures


class _StopAfterCapture(Exception):
    """create_engine / create_async_engine に渡された引数を捕捉した直後に

    フィクスチャの実行を打ち切るためだけの例外。実際の DB 接続や
    Base.metadata.create_all を発生させずに、渡された URL/kwargs だけを検証する。
    """


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


class TestEngineKwargsForUrl:
    """RepomConfig.engine_kwargs_for_url が URL のドライバーだけで

    SQLite（:memory: / ファイル）と PostgreSQL の kwargs を切り替えることを確認する。
    """

    def test_in_memory_sqlite_shape(self):
        kwargs = config.engine_kwargs_for_url("sqlite:///:memory:")
        assert kwargs["poolclass"] is StaticPool
        assert kwargs["connect_args"] == {"check_same_thread": False}
        assert kwargs["hide_parameters"] == config.sqlalchemy_hide_parameters

    def test_postgres_url_shape_regardless_of_configured_db_type(self, monkeypatch):
        monkeypatch.setattr(config, "db_type", "sqlite")

        kwargs = config.engine_kwargs_for_url("postgresql+psycopg://u:p@h/db")

        assert kwargs["pool_size"] == config.db_pool_size
        assert kwargs["max_overflow"] == config.db_max_overflow
        assert kwargs["pool_timeout"] == config.db_pool_timeout
        assert kwargs["pool_recycle"] == config.db_pool_recycle
        assert kwargs["pool_pre_ping"] == config.db_pool_pre_ping
        assert kwargs["connect_args"] == {
            "connect_timeout": config.db_connect_timeout,
            "application_name": config.db_application_name,
        }

    def test_engine_kwargs_matches_engine_kwargs_for_url_of_db_url(self):
        assert config.engine_kwargs == config.engine_kwargs_for_url(config.db_url)


class TestConvertToAsyncUriReExport:
    """repom.testing.convert_to_async_uri が repom.database.convert_to_async_uri の

    別名（同一オブジェクト）であることを確認する（repom#166 の重複実装解消）。
    """

    def test_is_same_function_object_as_database_module(self):
        assert testing_module.convert_to_async_uri is database_convert_to_async_uri

    def test_converts_psycopg_url_to_asyncpg(self):
        result = testing_module.convert_to_async_uri("postgresql+psycopg://u:p@h/db")
        assert result == "postgresql+asyncpg://u:p@h/db"


class TestResolveEngineSettings:
    """DatabaseManager.resolve_engine_settings が sync 側をそのまま返し、

    async 側だけドライバー変換 + asyncpg 用 connect_args 変換を行うことを確認する。
    """

    def test_sync_pair_unchanged_and_async_pair_adapted(self):
        sync_url = "postgresql+psycopg://u:p@h/db"
        engine_kwargs = {
            "pool_size": 5,
            "connect_args": {"connect_timeout": 7, "application_name": "repom"},
        }

        (result_sync_url, result_sync_kwargs), (async_url, async_kwargs) = (
            DatabaseManager.resolve_engine_settings(sync_url, engine_kwargs)
        )

        assert result_sync_url == sync_url
        assert result_sync_kwargs == engine_kwargs

        url = make_url(async_url)
        assert url.drivername == "postgresql+asyncpg"
        assert async_kwargs["pool_size"] == 5
        assert async_kwargs["connect_args"] == {
            "timeout": 7,
            "server_settings": {"application_name": "repom"},
        }
