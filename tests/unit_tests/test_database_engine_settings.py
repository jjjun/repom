"""DatabaseManager engine URL and keyword adaptation tests."""

import ssl
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
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
        ({"socket_timeout": 5}, "Unsupported PostgreSQL connect_args"),
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


def test_prod_query_host_override_requires_tls_for_sync_and_async(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    sync_url = (
        "postgresql+psycopg://user:pass@localhost/app"
        "?host=db.example.invalid"
    )

    (resolved_sync_url, sync_kwargs), (async_url, async_kwargs) = (
        DatabaseManager.resolve_engine_settings(sync_url, {})
    )

    sync_args, sync_connect_args = PGDialect_psycopg().create_connect_args(
        make_url(resolved_sync_url)
    )
    async_args, async_connect_args = PGDialect_asyncpg().create_connect_args(
        make_url(async_url)
    )
    sync_connect_args.update(sync_kwargs.get("connect_args", {}))
    async_connect_args.update(async_kwargs.get("connect_args", {}))

    assert sync_args == []
    assert async_args == []
    assert sync_connect_args["host"] == "db.example.invalid"
    assert sync_connect_args["sslmode"] == "require"
    assert async_connect_args["host"] == "db.example.invalid"
    assert async_connect_args["ssl"] == "require"


def test_prod_repeated_fallback_hosts_are_checked_for_sync_and_async(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    sync_url = (
        "postgresql+psycopg:///app?host=localhost:5432"
        "&host=db.example.invalid:5432"
    )

    (resolved_sync_url, sync_kwargs), (async_url, async_kwargs) = (
        DatabaseManager.resolve_engine_settings(sync_url, {})
    )

    _, sync_connect_args = PGDialect_psycopg().create_connect_args(
        make_url(resolved_sync_url)
    )
    _, async_connect_args = PGDialect_asyncpg().create_connect_args(
        make_url(async_url)
    )
    sync_connect_args.update(sync_kwargs.get("connect_args", {}))
    async_connect_args.update(async_kwargs.get("connect_args", {}))

    assert sync_connect_args["host"] == "localhost,db.example.invalid"
    assert sync_connect_args["port"] == "5432,5432"
    assert sync_connect_args["sslmode"] == "require"
    assert async_connect_args["host"] == ["localhost", "db.example.invalid"]
    assert async_connect_args["port"] == [5432, 5432]
    assert async_connect_args["ssl"] == "require"


@pytest.mark.parametrize(
    "sync_url",
    [
        "postgresql+psycopg://localhost/app?host=db.example.invalid&sslmode=disable",
        "postgresql+psycopg:///app?host=db.example.invalid&sslmode=prefer",
        "postgresql+psycopg://localhost/app?host=localhost,db.example.invalid&sslmode=allow",
        "postgresql+psycopg://localhost/app?hostaddr=198.51.100.5&sslmode=prefer",
    ],
)
def test_prod_rejects_weak_tls_for_remote_url_overrides(monkeypatch, sync_url):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))

    with pytest.raises(ValueError, match="sslmode"):
        DatabaseManager.resolve_engine_settings(sync_url, {})


@pytest.mark.parametrize(
    ("connect_args", "expected_host_key", "expected_host"),
    [
        ({"host": "db.example.invalid"}, "host", "db.example.invalid"),
        ({"hostaddr": "198.51.100.5"}, "hostaddr", "198.51.100.5"),
    ],
)
def test_prod_connect_args_destination_override_requires_sync_tls(
    monkeypatch, connect_args, expected_host_key, expected_host
):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    connect_args["sslmode"] = "require"

    sync_url, resolved_kwargs, _, _ = database_module._resolve_postgres_engine_policy(
        "postgresql+psycopg://user:pass@localhost/app?sslmode=prefer",
        {"connect_args": connect_args},
    )

    _, driver_args = PGDialect_psycopg().create_connect_args(make_url(sync_url))
    driver_args.update(resolved_kwargs["connect_args"])

    assert driver_args[expected_host_key] == expected_host
    assert driver_args["sslmode"] == "require"


def test_prod_connect_args_remote_override_rejects_weak_tls(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))

    with pytest.raises(ValueError, match="sslmode"):
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://user:pass@localhost/app?sslmode=prefer",
            {"connect_args": {"host": "db.example.invalid"}},
        )


def test_prod_connect_args_host_override_is_effective_for_both_drivers(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    engine_kwargs = {
        "connect_args": {"host": "db.example.invalid", "sslmode": "require"}
    }

    (sync_url, sync_kwargs), (async_url, async_kwargs) = (
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://user:pass@localhost/app?sslmode=prefer",
            engine_kwargs,
        )
    )

    _, sync_connect_args = PGDialect_psycopg().create_connect_args(make_url(sync_url))
    _, async_connect_args = PGDialect_asyncpg().create_connect_args(make_url(async_url))
    sync_connect_args.update(sync_kwargs["connect_args"])
    async_connect_args.update(async_kwargs["connect_args"])

    assert sync_connect_args["host"] == "db.example.invalid"
    assert sync_connect_args["sslmode"] == "require"
    assert async_connect_args["host"] == "db.example.invalid"
    assert async_connect_args["ssl"] == "require"


@pytest.mark.parametrize(
    "sync_url",
    [
        "postgresql+psycopg:///app?host=/var/run/postgresql&sslmode=prefer",
        "postgresql+psycopg://localhost/app?sslmode=prefer",
        "postgresql+psycopg://[::1]/app?sslmode=prefer",
    ],
)
def test_prod_local_socket_and_loopback_keep_weak_tls_exception(monkeypatch, sync_url):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))

    (resolved_sync_url, _), _ = DatabaseManager.resolve_engine_settings(
        sync_url, {}, environ={"PGHOST": "db.example.invalid"}
    )

    assert make_url(resolved_sync_url).query["sslmode"] == "prefer"


def test_prod_asyncpg_rejects_hostaddr_override(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))

    with pytest.raises(ValueError, match="Unsupported postgresql\\+asyncpg URL"):
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://user:pass@localhost/app"
            "?hostaddr=198.51.100.5&sslmode=require",
            {},
        )


def test_prod_asyncpg_rejects_unresolved_dsn_override(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))

    with pytest.raises(ValueError, match="DSN overrides"):
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://user:pass@localhost/app?sslmode=require",
            {"connect_args": {"dsn": "postgresql://remote.example/app"}},
        )


def test_prod_tls_warning_uses_the_effective_url_destination(monkeypatch, caplog):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    caplog.set_level("WARNING", logger="repom.database")

    database_module._warn_if_prod_sslmode_not_enforced(
        "postgresql+psycopg://db.example.invalid/app?host=localhost&sslmode=prefer",
        {},
    )

    assert "destination 'localhost'" in caplog.text
    assert "db.example.invalid" not in caplog.text


def test_prod_tls_warning_does_not_label_remote_override_as_localhost(monkeypatch, caplog):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    caplog.set_level("WARNING", logger="repom.database")

    database_module._warn_if_prod_sslmode_not_enforced(
        "postgresql+psycopg://localhost/app?host=db.example.invalid&sslmode=prefer",
        {},
    )

    assert not caplog.records


@pytest.mark.parametrize(
    "sync_url",
    [
        "postgresql+psycopg:///app",
        "postgresql+psycopg:///app?host=",
    ],
)
def test_prod_hostless_url_uses_remote_pghost_for_sync_and_async_tls(sync_url):
    environment = {"PGHOST": "db.example.invalid"}
    policy_config = RepomConfig(exec_env="prod")

    sync_url, sync_kwargs, sslmode, hosts = database_module._resolve_postgres_engine_policy(
        sync_url, {}, config_obj=policy_config, environ=environment
    )
    async_url, async_kwargs = DatabaseManager._adapt_asyncpg_connect_options(
        DatabaseManager._convert_to_async_uri(sync_url), sync_kwargs
    )

    _, sync_connect_args = PGDialect_psycopg().create_connect_args(make_url(sync_url))
    _, async_connect_args = PGDialect_asyncpg().create_connect_args(make_url(async_url))
    sync_connect_args.update(sync_kwargs.get("connect_args", {}))
    async_connect_args.update(async_kwargs.get("connect_args", {}))

    assert sslmode == "require"
    assert hosts == ("db.example.invalid",)
    assert sync_connect_args["sslmode"] == "require"
    assert async_connect_args["ssl"] == "require"


@pytest.mark.parametrize(
    ("sync_url", "connect_args", "environment"),
    [
        (
            "postgresql+psycopg:///app?service=remote_service",
            {},
            {},
        ),
        (
            "postgresql+psycopg:///app",
            {"service": "remote_service"},
            {},
        ),
        (
            "postgresql+psycopg:///app",
            {},
            {"PGSERVICE": "remote_service"},
        ),
    ],
)
def test_prod_service_fallback_is_unresolved_and_requires_tls(
    sync_url, connect_args, environment
):
    policy_config = RepomConfig(exec_env="prod")

    resolved_url, _, sslmode, hosts = database_module._resolve_postgres_engine_policy(
        sync_url,
        {"connect_args": connect_args} if connect_args else {},
        config_obj=policy_config,
        environ=environment,
    )

    assert make_url(resolved_url).query["sslmode"] == "require"
    assert sslmode == "require"
    assert hosts == ("<service destination>",)


@pytest.mark.parametrize(
    ("sync_url", "environment", "expected_hosts"),
    [
        (
            "postgresql+psycopg://localhost/app",
            {"PGHOSTADDR": "198.51.100.5"},
            ("198.51.100.5",),
        ),
        (
            "postgresql+psycopg:///app",
            {"PGHOST": "localhost,db.example.invalid"},
            ("localhost", "db.example.invalid"),
        ),
    ],
)
def test_prod_environment_destination_fallbacks_require_tls(
    sync_url, environment, expected_hosts
):
    resolved_url, _, sslmode, hosts = database_module._resolve_postgres_engine_policy(
        sync_url,
        {},
        config_obj=RepomConfig(exec_env="prod"),
        environ=environment,
    )

    assert make_url(resolved_url).query["sslmode"] == "require"
    assert sslmode == "require"
    assert hosts == expected_hosts


def test_prod_pgsslmode_is_validated_and_adapted_for_both_drivers():
    environment = {
        "PGHOST": "db.example.invalid",
        "PGSSLMODE": "verify-full",
    }
    policy_config = RepomConfig(exec_env="prod")
    sync_url, sync_kwargs, sslmode, _ = database_module._resolve_postgres_engine_policy(
        "postgresql+psycopg:///app",
        {},
        config_obj=policy_config,
        environ=environment,
    )
    async_url, async_kwargs = DatabaseManager._adapt_asyncpg_connect_options(
        DatabaseManager._convert_to_async_uri(sync_url), sync_kwargs
    )

    _, sync_connect_args = PGDialect_psycopg().create_connect_args(make_url(sync_url))
    _, async_connect_args = PGDialect_asyncpg().create_connect_args(make_url(async_url))
    sync_connect_args.update(sync_kwargs.get("connect_args", {}))
    async_connect_args.update(async_kwargs.get("connect_args", {}))

    assert sslmode == "verify-full"
    assert sync_connect_args["sslmode"] == "verify-full"
    assert async_connect_args["ssl"] == "verify-full"


def test_config_db_url_uses_environment_destination_and_pgsslmode(monkeypatch):
    monkeypatch.setenv("PGHOST", "db.example.invalid")
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.setenv("PGSSLMODE", "verify-full")
    policy_config = RepomConfig(exec_env="prod")
    policy_config.db_url = "postgresql+psycopg:///app"

    resolved_url = make_url(policy_config.db_url)

    assert resolved_url.query["sslmode"] == "verify-full"


def test_prod_rejects_weak_pgsslmode_for_remote_environment_destination():
    with pytest.raises(ValueError, match="sslmode"):
        database_module._resolve_postgres_engine_policy(
            "postgresql+psycopg:///app",
            {},
            config_obj=RepomConfig(exec_env="prod"),
            environ={"PGHOST": "db.example.invalid", "PGSSLMODE": "prefer"},
        )


def test_prod_hostless_url_without_environment_destination_keeps_local_prefer():
    resolved_url, _, sslmode, hosts = database_module._resolve_postgres_engine_policy(
        "postgresql+psycopg:///app",
        {},
        config_obj=RepomConfig(exec_env="prod"),
        environ={},
    )

    assert make_url(resolved_url).query.get("sslmode") is None
    assert sslmode == "prefer"
    assert hosts == (None,)


@pytest.mark.parametrize("exec_env", ["dev", "prod"])
@pytest.mark.parametrize("host", ["localhost", "db.example.invalid"])
def test_configured_sslmode_is_materialized_into_raw_url(exec_env, host):
    policy_config = RepomConfig(exec_env=exec_env)
    policy_config.postgres.sslmode = "verify-full"
    engine_kwargs = {}

    resolved_url, resolved_kwargs, sslmode, _ = (
        database_module._resolve_postgres_engine_policy(
            f"postgresql+psycopg://{host}/app",
            engine_kwargs,
            config_obj=policy_config,
            environ={},
        )
    )

    assert make_url(resolved_url).query["sslmode"] == "verify-full"
    assert sslmode == "verify-full"
    assert resolved_kwargs is engine_kwargs


def test_configured_sslmode_does_not_override_url_or_connect_args_tls():
    policy_config = RepomConfig(exec_env="dev")
    policy_config.postgres.sslmode = "verify-full"
    url_with_mode = "postgresql+psycopg://localhost/app?sslmode=prefer"

    resolved_url, _, sslmode, _ = database_module._resolve_postgres_engine_policy(
        url_with_mode, {}, config_obj=policy_config, environ={}
    )
    assert resolved_url == url_with_mode
    assert sslmode == "prefer"

    for connect_args in ({"sslmode": "require"}, {"ssl": "require"}):
        resolved_url, _, _, _ = database_module._resolve_postgres_engine_policy(
            "postgresql+psycopg://localhost/app",
            {"connect_args": connect_args},
            config_obj=policy_config,
            environ={},
        )
        assert "sslmode" not in make_url(resolved_url).query


def test_unset_sslmode_keeps_raw_url_unchanged_in_dev():
    policy_config = RepomConfig(exec_env="dev")
    raw_url = "postgresql+psycopg://localhost/app"

    resolved_url, _, sslmode, _ = database_module._resolve_postgres_engine_policy(
        raw_url, {}, config_obj=policy_config, environ={}
    )

    assert resolved_url == raw_url
    assert sslmode == "prefer"


def test_configured_sslmode_and_sslrootcert_reach_both_drivers(monkeypatch):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    create_context_calls = []

    def create_default_context(*, cafile=None):
        create_context_calls.append(cafile)
        return ssl_context

    monkeypatch.setattr(database_module.ssl, "create_default_context", create_default_context)
    policy_config = RepomConfig(exec_env="dev")
    policy_config.postgres.sslmode = "verify-full"
    policy_config.postgres.sslrootcert = "configured-ca.pem"
    monkeypatch.setattr(database_module, "config", policy_config)

    (sync_url, sync_kwargs), (async_url, async_kwargs) = (
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://u:p@localhost/app", {}, environ={}
        )
    )

    sync_query = make_url(sync_url).query
    assert sync_query["sslmode"] == "verify-full"
    assert sync_query["sslrootcert"] == "configured-ca.pem"
    assert sync_kwargs == {}
    assert make_url(async_url).drivername == "postgresql+asyncpg"
    assert create_context_calls == ["configured-ca.pem"]
    assert async_kwargs["connect_args"]["ssl"] is ssl_context
    assert ssl_context.check_hostname is True


def test_configured_sslmode_without_sslrootcert_reaches_asyncpg(monkeypatch):
    policy_config = RepomConfig(exec_env="dev")
    policy_config.postgres.sslmode = "require"
    monkeypatch.setattr(database_module, "config", policy_config)

    (sync_url, _), (_, async_kwargs) = DatabaseManager.resolve_engine_settings(
        "postgresql+psycopg://u:p@localhost/app", {}, environ={}
    )

    sync_query = make_url(sync_url).query
    assert sync_query["sslmode"] == "require"
    assert "sslrootcert" not in sync_query
    assert async_kwargs["connect_args"]["ssl"] == "require"


def test_url_sslrootcert_is_kept_over_configured_sslrootcert():
    policy_config = RepomConfig(exec_env="dev")
    policy_config.postgres.sslmode = "verify-full"
    policy_config.postgres.sslrootcert = "configured-ca.pem"

    resolved_url, _, _, _ = database_module._resolve_postgres_engine_policy(
        "postgresql+psycopg://localhost/app?sslrootcert=url-ca.pem",
        {},
        config_obj=policy_config,
        environ={},
    )

    assert make_url(resolved_url).query["sslrootcert"] == "url-ca.pem"


@pytest.mark.parametrize("sslmode, check_hostname", [("verify-ca", False), ("verify-full", True)])
def test_asyncpg_sslrootcert_system_uses_the_platform_trust_store(
    monkeypatch, sslmode, check_hostname
):
    create_context_calls = []
    real_create_default_context = ssl.create_default_context

    def create_default_context(*args, **kwargs):
        create_context_calls.append((args, kwargs))
        return real_create_default_context()

    monkeypatch.setattr(database_module.ssl, "create_default_context", create_default_context)

    (_, _), (_, async_kwargs) = DatabaseManager.resolve_engine_settings(
        "postgresql+psycopg://u:p@db.example.invalid/app"
        f"?sslmode={sslmode}&sslrootcert=system",
        {},
        environ={},
    )

    assert create_context_calls == [((), {})]
    context = async_kwargs["connect_args"]["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is check_hostname


@pytest.mark.parametrize("exec_env", ["dev", "prod"])
@pytest.mark.parametrize(
    ("sync_url", "carrier", "connect_args"),
    [
        (
            "postgresql+psycopg://localhost/app?sslmode=prefer",
            "conninfo",
            {"conninfo": "hostaddr=203.0.113.5 sslmode=disable"},
        ),
        (
            "postgresql+psycopg:///app",
            "conninfo",
            {"conninfo": "host=db.example.invalid sslmode=disable"},
        ),
        (
            "postgresql+psycopg://db.example.invalid/app?sslmode=require",
            "requiressl",
            {"requiressl": "0"},
        ),
    ],
)
def test_psycopg_connection_string_carriers_are_rejected(
    exec_env, sync_url, carrier, connect_args
):
    with pytest.raises(
        ValueError, match=f"Unsupported PostgreSQL connect_args.*'{carrier}'"
    ) as excinfo:
        database_module._resolve_postgres_engine_policy(
            sync_url,
            {"connect_args": connect_args},
            config_obj=RepomConfig(exec_env=exec_env),
            environ={},
        )

    assert "203.0.113.5" not in str(excinfo.value)
    assert "db.example.invalid" not in str(excinfo.value)


def test_prod_resolve_engine_settings_rejects_conninfo_destination(monkeypatch):
    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))

    with pytest.raises(ValueError, match="'conninfo'"):
        DatabaseManager.resolve_engine_settings(
            "postgresql+psycopg://localhost/app?sslmode=prefer",
            {"connect_args": {"conninfo": "hostaddr=203.0.113.5 sslmode=disable"}},
        )


def test_prod_get_sync_engine_rejects_conninfo_destination(monkeypatch):
    policy_config = RepomConfig(exec_env="prod")
    monkeypatch.setattr(
        database_module,
        "config",
        SimpleNamespace(
            exec_env="prod",
            db_url="postgresql+psycopg://localhost/app?sslmode=prefer",
            engine_kwargs={
                "connect_args": {"conninfo": "hostaddr=203.0.113.5 sslmode=disable"}
            },
            postgres_tls_settings_for_url=policy_config.postgres_tls_settings_for_url,
        ),
    )

    def create_engine_must_not_run(*args, **kwargs):
        raise AssertionError("create_engine must not run for a rejected carrier")

    monkeypatch.setattr(database_module, "create_engine", create_engine_must_not_run)
    manager = DatabaseManager()

    with pytest.raises(ValueError, match="'conninfo'"):
        manager.get_sync_engine()

    assert manager._sync_engine is None


@pytest.mark.parametrize(
    "connect_args",
    [
        {"conninfo": "hostaddr=203.0.113.5 sslmode=disable"},
        {"socket_timeout": 5},
    ],
)
def test_asyncpg_adapter_still_rejects_unsupported_connect_args(connect_args):
    with pytest.raises(ValueError, match="Unsupported postgresql\\+asyncpg connect_args"):
        DatabaseManager._adapt_asyncpg_connect_options(
            "postgresql+asyncpg://u:p@h/db", {"connect_args": connect_args}
        )


def test_postgres_connect_args_allowlist_keeps_supported_keywords():
    connect_args = {
        "connect_timeout": 7,
        "application_name": "repom",
        "options": "-csearch_path=app",
        "keepalives": 1,
        "sslrootcert": "ca.pem",
        "server_settings": {"statement_timeout": "1000"},
        "timeout": 3,
    }
    engine_kwargs = {"connect_args": connect_args}

    _, resolved_kwargs, _, _ = database_module._resolve_postgres_engine_policy(
        "postgresql+psycopg://u:p@h/db?sslmode=require",
        engine_kwargs,
        config_obj=RepomConfig(exec_env="prod"),
        environ={},
    )

    assert resolved_kwargs is engine_kwargs


def test_postgres_connect_args_allowlist_covers_installed_libpq_keywords():
    pq = pytest.importorskip("psycopg.pq")

    libpq_keywords = {
        option.keyword.decode() for option in pq.Conninfo.get_defaults()
    }

    assert libpq_keywords <= database_module._POSTGRES_CONNECT_ARGUMENTS
    assert "conninfo" not in database_module._POSTGRES_CONNECT_ARGUMENTS
    assert "requiressl" not in database_module._POSTGRES_CONNECT_ARGUMENTS


def test_prod_non_postgres_override_has_no_transport_guard():
    policy_config = RepomConfig(exec_env="prod")
    mysql_url = "mysql+pymysql://u:p@db.example.invalid/app"
    engine_kwargs = {"connect_args": {"ssl_disabled": True}}

    policy_config.db_url = mysql_url
    resolved_url, resolved_kwargs, sslmode, hosts = (
        database_module._resolve_postgres_engine_policy(
            mysql_url, engine_kwargs, config_obj=policy_config, environ={}
        )
    )

    assert policy_config.db_url == mysql_url
    assert resolved_url == mysql_url
    assert resolved_kwargs is engine_kwargs
    assert sslmode is None
    assert hosts == ()
