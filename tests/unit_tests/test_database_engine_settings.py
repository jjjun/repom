"""DatabaseManager engine URL and keyword adaptation tests."""

from sqlalchemy.engine.url import make_url

from repom.config import RepomConfig
from repom.database import DatabaseManager


def test_resolve_engine_settings_keeps_sync_pair_and_adapts_async_pair():
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


def test_prod_postgres_override_resolves_sslmode_for_async_engine():
    config = RepomConfig(exec_env="prod")
    config.db_url = "postgresql+psycopg://user:secret@db.example.internal/appdb"

    (_, _), (async_url, async_kwargs) = DatabaseManager.resolve_engine_settings(
        config.db_url, {}
    )

    assert make_url(async_url).drivername == "postgresql+asyncpg"
    assert async_kwargs["connect_args"]["ssl"] == "require"
