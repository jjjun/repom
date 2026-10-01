"""DatabaseManager engine URL and keyword adaptation tests."""

import ssl

import pytest
from sqlalchemy.engine.url import make_url

from repom.config import RepomConfig
from repom.database import DatabaseManager
import repom.database as database_module


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


def test_connect_args_override_url_tls_and_preserve_asyncpg_options(monkeypatch):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    create_context_calls = []

    def create_default_context(*, cafile=None):
        create_context_calls.append(cafile)
        return ssl_context

    monkeypatch.setattr(database_module.ssl, "create_default_context", create_default_context)

    def password_callback():
        return "synthetic-password"

    connect_args = {
        "sslmode": "verify-full",
        "sslrootcert": "connect-ca.pem",
        "connect_timeout": 7,
        "application_name": "audit",
        "password": password_callback,
        "server_settings": {"statement_timeout": "1000"},
    }
    original_connect_args = {
        **connect_args,
        "server_settings": dict(connect_args["server_settings"]),
    }
    engine_kwargs = {"connect_args": connect_args}
    sync_url = (
        "postgresql+psycopg://u:p@db.example.invalid/app"
        "?sslmode=require&sslrootcert=url-ca.pem"
    )

    (result_sync_url, result_sync_kwargs), (async_url, async_kwargs) = (
        DatabaseManager.resolve_engine_settings(sync_url, engine_kwargs)
    )

    assert result_sync_url == sync_url
    assert result_sync_kwargs is engine_kwargs
    assert connect_args == original_connect_args
    assert "sslmode" not in make_url(async_url).query
    assert "sslrootcert" not in make_url(async_url).query
    assert create_context_calls == ["connect-ca.pem"]
    assert async_kwargs["connect_args"] == {
        "ssl": ssl_context,
        "timeout": 7,
        "password": password_callback,
        "server_settings": {
            "statement_timeout": "1000",
            "application_name": "audit",
        },
    }
    assert async_kwargs["connect_args"]["ssl"].check_hostname is True


def test_native_asyncpg_ssl_context_overrides_url_and_keeps_input_unchanged():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def password_callback():
        return "synthetic-password"

    connect_args = {
        "ssl": ssl_context,
        "timeout": 3,
        "password": password_callback,
        "server_settings": {"statement_timeout": "1000"},
    }
    original_connect_args = {
        **connect_args,
        "server_settings": dict(connect_args["server_settings"]),
    }
    engine_kwargs = {"connect_args": connect_args}

    _, (async_url, async_kwargs) = DatabaseManager.resolve_engine_settings(
        "postgresql+psycopg://u:p@h/db?sslmode=require", engine_kwargs
    )

    assert "sslmode" not in make_url(async_url).query
    assert async_kwargs["connect_args"]["ssl"] is ssl_context
    assert async_kwargs["connect_args"]["timeout"] == 3
    assert async_kwargs["connect_args"]["password"] is password_callback
    assert async_kwargs["connect_args"]["server_settings"] == {
        "statement_timeout": "1000"
    }
    assert connect_args == original_connect_args


@pytest.mark.parametrize(
    ("connect_args", "message"),
    [
        ({"socket_timeout": 5}, "Unsupported postgresql\\+asyncpg connect_args"),
        (
            {"connect_timeout": 7, "timeout": 3},
            "connect_timeout.*conflicts.*timeout",
        ),
        (
            {
                "application_name": "audit",
                "server_settings": {"application_name": "worker"},
            },
            "application_name.*conflicts.*server_settings",
        ),
        (
            {"ssl": ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "sslmode": "require"},
            "conflicts with libpq SSL",
        ),
    ],
)
def test_unsupported_or_conflicting_asyncpg_connect_args_raise(connect_args, message):
    with pytest.raises(ValueError, match=message):
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://u:p@h/db?sslmode=require",
            {"connect_args": connect_args},
        )
