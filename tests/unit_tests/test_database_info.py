"""Tests for database diagnostics helpers."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from repom.diagnostics import database_info
import repom.database as database_module
from repom.config import RepomConfig
from repom.database import DatabaseManager
from repom.diagnostics.database_info import (
    collect_database_info_async,
    collect_database_info_sync,
    format_size,
    resolve_sqlite_db_path,
    short_lived_postgres_engine,
)


def _postgres_probe_config(engine_kwargs, *, exec_env="dev", db_url=None):
    policy_config = RepomConfig(exec_env=exec_env)
    return SimpleNamespace(
        db_type="postgres",
        db_url=db_url or "postgresql://user:pass@localhost:5432/app",
        db_name="app",
        postgres_db="app_dev",
        engine_kwargs=engine_kwargs,
        exec_env=exec_env,
        postgres_tls_settings_for_url=policy_config.postgres_tls_settings_for_url,
    )


def test_format_size_auto_units():
    assert format_size(None) == "N/A"
    assert format_size(512) == "512 B"
    assert format_size(1024) == "1.00 KB"
    assert format_size(1024 * 1024) == "1.00 MB"


def test_format_size_fixed_mb():
    assert format_size(1024 * 1024, unit="mb") == "1.00 MB"
    assert format_size(0, unit="mb") == "0.00 MB"


def test_resolve_sqlite_db_path_uses_process_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    relative = resolve_sqlite_db_path("sqlite:///data/app.sqlite3")
    assert relative == tmp_path / "data" / "app.sqlite3"

    absolute_db = tmp_path / "absolute.sqlite3"
    absolute = resolve_sqlite_db_path(f"sqlite:///{absolute_db}")
    assert absolute == absolute_db

    assert resolve_sqlite_db_path("sqlite:///:memory:") is None
    assert resolve_sqlite_db_path("postgresql://localhost/db") is None


def test_resolve_sqlite_db_path_uses_make_url(monkeypatch, tmp_path):
    """A driver-qualified scheme and a query string must be parsed correctly
    (repom#163) - a literal-prefix check misreads both.
    """
    monkeypatch.chdir(tmp_path)
    driver_qualified = resolve_sqlite_db_path(
        "sqlite+pysqlite:///data/app.sqlite3"
    )
    assert driver_qualified == tmp_path / "data" / "app.sqlite3"

    with_query_string = resolve_sqlite_db_path(
        "sqlite:///data/app.sqlite3?timeout=30"
    )
    assert with_query_string == tmp_path / "data" / "app.sqlite3"

    assert resolve_sqlite_db_path("sqlite://") is None


@pytest.mark.parametrize(
    "db_url",
    [
        "sqlite:///relative.db?uri=true",
        "sqlite:///file:relative.db?uri=true",
        "sqlite:///file:memorydb?mode=memory&cache=shared&uri=true",
        "sqlite:///file:relative.db",
    ],
)
def test_resolve_sqlite_db_path_rejects_uri_urls(db_url):
    assert resolve_sqlite_db_path(db_url) is None


def test_collect_database_info_sync_sqlite_file(tmp_path):
    db_file = tmp_path / "app.sqlite3"
    db_file.write_bytes(b"1234")
    mock_config = SimpleNamespace(
        db_type="sqlite",
        db_url=f"sqlite:///{db_file}",
        root_path=tmp_path,
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = collect_database_info_sync()

    assert info.backend == "sqlite"
    assert info.target == str(db_file)
    assert info.size_bytes == 4
    assert info.size_text == "4 B"
    assert info.status == "ok"


def test_collect_database_info_sync_sqlite_missing_file(tmp_path):
    db_file = tmp_path / "missing.sqlite3"
    mock_config = SimpleNamespace(
        db_type="sqlite",
        db_url=f"sqlite:///{db_file}",
        root_path=tmp_path,
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = collect_database_info_sync()

    assert info.backend == "sqlite"
    assert info.target == str(db_file)
    assert info.size_bytes == 0
    assert info.size_text == "0 B"
    assert info.status == "unavailable"
    assert info.error == "SQLite database file not found"


def test_collect_database_info_sync_sqlite_relative_file_uses_cwd(
    monkeypatch, tmp_path
):
    cwd = tmp_path / "sqlite-cwd"
    root = tmp_path / "sqlite-root"
    cwd.mkdir()
    root.mkdir()
    cwd_db = cwd / "target.sqlite3"
    root_db = root / "target.sqlite3"
    cwd_db.write_bytes(b"cwd")
    root_db.write_bytes(b"root")
    mock_config = SimpleNamespace(
        db_type="sqlite",
        db_url="sqlite:///target.sqlite3",
        root_path=root,
    )
    monkeypatch.chdir(cwd)

    with patch.object(database_info.config_module, "config", mock_config):
        info = collect_database_info_sync()

    assert info.target == str(cwd_db)
    assert info.size_bytes == 3
    assert info.status == "ok"


def test_collect_database_info_sync_sqlite_memory(tmp_path):
    mock_config = SimpleNamespace(
        db_type="sqlite",
        db_url="sqlite:///:memory:",
        root_path=tmp_path,
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = collect_database_info_sync()

    assert info.backend == "sqlite"
    assert info.target == ":memory:"
    assert info.size_bytes is None
    assert info.size_text == "N/A (in-memory)"
    assert info.status == "ok"
    assert info.error == ""


def test_collect_database_info_sync_sqlite_uri_is_unsupported(tmp_path):
    mock_config = SimpleNamespace(
        db_type="sqlite",
        db_url="sqlite:///file:relative.db?mode=memory&cache=shared&uri=true",
        root_path=tmp_path,
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = collect_database_info_sync()

    assert info.backend == "sqlite"
    assert info.target.startswith("sqlite:///file:relative.db?")
    assert "mode=memory" in info.target
    assert "uri=true" in info.target
    assert info.size_bytes is None
    assert info.size_text == "N/A (unsupported)"
    assert info.status == "unsupported"
    assert info.error == "SQLite URL is not a supported file-based database"
    assert not (tmp_path / "file:relative.db").exists()


def test_collect_database_info_sync_postgres_skips_size_query():
    mock_config = SimpleNamespace(
        db_type="postgres",
        db_url="postgresql://user:pass@localhost:5432/app",
        db_name="app",
        postgres_db="app_dev",
        engine_kwargs={"connect_args": {}},
    )

    with patch.object(database_info.config_module, "config", mock_config), patch.object(
        database_info, "create_engine"
    ) as mock_create_engine:
        info = collect_database_info_sync(include_database_size=False)

    assert info.backend == "postgres"
    assert info.target == "app_dev"
    assert info.size_bytes is None
    assert info.size_text == "N/A (skipped)"
    assert info.status == "ok"
    mock_create_engine.assert_not_called()


def test_collect_database_info_sync_postgres_reads_size():
    mock_config = _postgres_probe_config(
        {
            "pool_pre_ping": True,
            "connect_args": {"connect_timeout": 10, "application_name": "app"},
        }
    )
    mock_engine = Mock()
    mock_conn = Mock()
    mock_result = Mock()
    mock_result.scalar_one.return_value = 2 * 1024 * 1024
    mock_conn.execute.return_value = mock_result
    mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = Mock(return_value=False)

    with patch.object(database_info.config_module, "config", mock_config), patch.object(
        database_info, "create_engine", return_value=mock_engine
    ) as mock_create_engine:
        info = collect_database_info_sync()

    assert info.backend == "postgres"
    assert info.target == "app_dev"
    assert info.size_bytes == 2 * 1024 * 1024
    assert info.size_text == "2.00 MB"
    assert info.status == "ok"
    mock_engine.dispose.assert_called_once()

    # config.engine_kwargs must flow through (application_name preserved),
    # with only the connect timeout pinned to a short probe value.
    _, kwargs = mock_create_engine.call_args
    assert kwargs["connect_args"]["application_name"] == "app"
    assert kwargs["connect_args"]["connect_timeout"] == 3
    assert kwargs["pool_pre_ping"] is True


@pytest.mark.parametrize(
    ("connect_args", "error_match", "secret"),
    [
        (
            {"host": "remote.audit.invalid", "sslmode": "disable"},
            "sslmode",
            "probe_password",
        ),
        (
            {"hostaddr": "198.51.100.5", "sslmode": "allow"},
            "sslmode",
            "probe_password",
        ),
        (
            {"dsn": "host=remote.audit.invalid sslmode=disable password=dsn_secret"},
            "DSN",
            "dsn_secret",
        ),
    ],
)
def test_prod_normal_engine_and_database_info_probe_reject_unsafe_connect_args(
    monkeypatch, connect_args, error_match, secret
):
    db_url = "postgresql://user:probe_password@127.0.0.1:5432/app?sslmode=require"
    engine_kwargs = {"connect_args": connect_args}
    probe_config = _postgres_probe_config(
        engine_kwargs, exec_env="prod", db_url=db_url
    )

    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="prod"))
    with pytest.raises(ValueError, match=error_match):
        DatabaseManager.resolve_engine_settings(db_url, engine_kwargs)

    monkeypatch.setattr(database_module, "config", RepomConfig(exec_env="dev"))
    with patch.object(database_info.config_module, "config", probe_config), patch.object(
        database_info, "create_engine"
    ) as mock_create_engine:
        info = collect_database_info_sync()

    assert info.status == "unavailable"
    assert error_match.lower() in info.error.lower()
    assert secret not in info.error
    assert "probe_password" not in info.error
    mock_create_engine.assert_not_called()


@pytest.mark.parametrize(
    ("connect_args", "expected_sslmode"),
    [
        ({"host": "localhost", "sslmode": "disable"}, "disable"),
        ({"hostaddr": "198.51.100.5", "sslmode": "verify-full"}, "verify-full"),
    ],
)
def test_postgres_probe_keeps_local_and_strong_tls_settings(
    connect_args, expected_sslmode
):
    engine_kwargs = {"connect_args": connect_args}
    config_obj = _postgres_probe_config(
        engine_kwargs,
        exec_env="prod",
        db_url="postgresql://user:pass@localhost:5432/app?sslmode=require",
    )
    mock_engine = Mock()

    with patch.object(
        database_info, "create_engine", return_value=mock_engine
    ) as mock_create_engine:
        with short_lived_postgres_engine(config_obj):
            pass

    _, kwargs = mock_create_engine.call_args
    assert kwargs["connect_args"]["sslmode"] == expected_sslmode
    assert kwargs["connect_args"]["connect_timeout"] == 3
    assert "connect_timeout" not in engine_kwargs["connect_args"]
    assert engine_kwargs["connect_args"]["sslmode"] == expected_sslmode
    mock_engine.dispose.assert_called_once()


def test_collect_database_info_sync_postgres_disposes_engine_on_connect_error():
    """The engine must be disposed even when engine.connect() raises, not
    just when create_engine() raises - otherwise a failing check leaks the
    engine (repom#163).
    """
    mock_config = _postgres_probe_config({"connect_args": {}})
    mock_engine = Mock()
    mock_engine.connect.side_effect = RuntimeError("connection refused")

    with patch.object(database_info.config_module, "config", mock_config), patch.object(
        database_info, "create_engine", return_value=mock_engine
    ):
        info = collect_database_info_sync()

    assert info.status == "unavailable"
    assert "connection refused" in info.error
    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_collect_database_info_async_postgres_skips_size_query():
    mock_config = SimpleNamespace(
        db_type="postgres",
        db_url="postgresql://user:pass@localhost:5432/app",
        db_name="app",
        postgres_db="",
    )
    mock_session = Mock()

    with patch.object(database_info.config_module, "config", mock_config):
        info = await collect_database_info_async(
            mock_session,
            include_database_size=False,
        )

    assert info.backend == "postgres"
    assert info.target == "app"
    assert info.size_text == "N/A (skipped)"
    assert info.status == "ok"
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_collect_database_info_async_postgres_no_session_skips_size_matches_sync():
    """include_database_size must be evaluated before requiring a session, so
    a caller with no session but no need for the size still gets the same
    'ok' / skipped result the sync function returns (repom#163).
    """
    mock_config = SimpleNamespace(
        db_type="postgres",
        db_url="postgresql://user:pass@localhost:5432/app",
        db_name="app",
        postgres_db="app_dev",
        engine_kwargs={"connect_args": {}},
    )

    with patch.object(database_info.config_module, "config", mock_config):
        async_info = await collect_database_info_async(None, include_database_size=False)
        sync_info = collect_database_info_sync(include_database_size=False)

    assert async_info.status == sync_info.status == "ok"
    assert async_info.size_text == sync_info.size_text == "N/A (skipped)"
    assert async_info.target == sync_info.target == "app_dev"


@pytest.mark.asyncio
async def test_collect_database_info_async_postgres_requires_session_for_size():
    mock_config = SimpleNamespace(
        db_type="postgres",
        db_url="postgresql://user:pass@localhost:5432/app",
        db_name="app",
        postgres_db="app_dev",
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = await collect_database_info_async(None)

    assert info.status == "unavailable"
    assert info.error == "Async session is not available"


@pytest.mark.asyncio
async def test_collect_database_info_async_postgres_reads_size():
    mock_config = SimpleNamespace(
        db_type="postgres",
        db_url="postgresql://user:pass@localhost:5432/app",
        db_name="app",
        postgres_db="app_dev",
    )
    mock_result = Mock()
    mock_result.scalar_one.return_value = 1024

    class FakeSession:
        async def execute(self, _statement):
            return mock_result

    with patch.object(database_info.config_module, "config", mock_config):
        info = await collect_database_info_async(FakeSession())

    assert info.backend == "postgres"
    assert info.target == "app_dev"
    assert info.size_bytes == 1024
    assert info.size_text == "1.00 KB"
    assert info.status == "ok"


def test_collect_database_info_sync_unsupported_backend():
    ssl_password = "known-ssl-passphrase"
    mock_config = SimpleNamespace(
        db_type="mysql",
        db_url=(
            "mysql://user:known-password@localhost/app"
            f"?sslpassword={ssl_password}"
        ),
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = collect_database_info_sync()

    assert info.backend == "mysql"
    assert info.target == "mysql://user:***@localhost/app?sslpassword=***"
    assert "known-password" not in info.target
    assert ssl_password not in info.target
    assert info.status == "unsupported"
    assert "Unsupported database backend" in info.error


@pytest.mark.asyncio
async def test_collect_database_info_async_unsupported_backend_masks_password():
    ssl_password = "known-ssl-passphrase"
    mock_config = SimpleNamespace(
        db_type="mysql",
        db_url=(
            "mysql://user:known-password@localhost/app"
            f"?sslpassword={ssl_password}"
        ),
    )

    with patch.object(database_info.config_module, "config", mock_config):
        info = await collect_database_info_async()

    assert info.target == "mysql://user:***@localhost/app?sslpassword=***"
    assert "known-password" not in info.target
    assert ssl_password not in info.target
