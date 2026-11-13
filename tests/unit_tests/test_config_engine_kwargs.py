"""RepomConfig engine settings for supported database URL shapes."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from repom.config import RepomConfig


@pytest.mark.parametrize(
    ("url", "db_type", "exec_env", "in_memory", "hide_parameters", "uses_pool"),
    [
        pytest.param(None, "postgres", "dev", False, False, True, id="postgres-configured"),
        pytest.param(
            "postgresql+psycopg://u:p@h/db",
            "sqlite",
            "dev",
            False,
            True,
            True,
            id="postgres-url",
        ),
        pytest.param(None, "sqlite", "dev", False, True, True, id="sqlite-file"),
        pytest.param(None, "sqlite", "test", True, False, False, id="sqlite-memory"),
    ],
)
def test_engine_kwargs_for_database_urls(
    url, db_type, exec_env, in_memory, hide_parameters, uses_pool, tmp_path
):
    config = RepomConfig(exec_env=exec_env)
    config.db_type = db_type
    config.sqlalchemy_hide_parameters = hide_parameters

    if db_type == "sqlite":
        config.root_path = str(tmp_path)
        config.sqlite.use_in_memory_for_tests = in_memory
        config.init()

    config.db_pool_size = 5
    config.db_max_overflow = 7
    config.db_pool_timeout = 15
    config.db_pool_recycle = 1800
    config.db_pool_pre_ping = False

    kwargs = config.engine_kwargs_for_url(url or config.db_url)

    assert kwargs["hide_parameters"] is hide_parameters
    if (url or config.db_url).startswith("postgresql"):
        assert kwargs["connect_args"] == {
            "connect_timeout": config.db_connect_timeout,
            "application_name": config.db_application_name,
        }
    else:
        assert kwargs["connect_args"] == {"check_same_thread": False}

    if uses_pool:
        assert kwargs["pool_size"] == 5
        assert kwargs["max_overflow"] == 7
        assert kwargs["pool_timeout"] == 15
        assert kwargs["pool_recycle"] == 1800
        assert kwargs["pool_pre_ping"] is False
        assert "poolclass" not in kwargs
    else:
        assert kwargs["poolclass"] is StaticPool
        assert "pool_size" not in kwargs
        assert "max_overflow" not in kwargs


@pytest.mark.parametrize("db_type,exec_env", [("postgres", "dev"), ("sqlite", "test")])
def test_engine_kwargs_property_matches_url_settings(db_type, exec_env, tmp_path):
    config = RepomConfig(exec_env=exec_env)
    config.db_type = db_type
    config.root_path = str(tmp_path)
    config.init()

    assert config.engine_kwargs == config.engine_kwargs_for_url(config.db_url)


def _create_engine_for_url(url, kwargs):
    if "aiosqlite" in url:
        return create_async_engine(url, **kwargs).sync_engine
    return create_engine(url, **kwargs)


@pytest.mark.parametrize("driver", ["sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"])
@pytest.mark.parametrize(
    "target",
    [
        "",
        "/:memory:",
        "/file:memdb?mode=memory&uri=true",
        "/file:memdb?mode=memory&cache=shared&uri=true",
        "/file::memory:?cache=shared&uri=true",
        "/file:///tmp/memdb?mode=memory&uri=true",
    ],
    ids=["bare", "memory", "uri-mode", "uri-shared", "uri-memory-name", "uri-path"],
)
def test_engine_kwargs_for_sqlite_memory_urls_use_static_pool(driver, target):
    url = f"{driver}://{target}"
    config = RepomConfig(exec_env="dev")

    kwargs = config.engine_kwargs_for_url(url)

    assert kwargs["poolclass"] is StaticPool
    assert kwargs["connect_args"] == {"check_same_thread": False}
    assert not {"pool_size", "max_overflow", "pool_timeout"} & kwargs.keys()
    # create_engine rejects pool options that the pool SQLAlchemy selects lacks
    engine = _create_engine_for_url(url, kwargs)
    engine.dispose()


@pytest.mark.parametrize("driver", ["sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"])
@pytest.mark.parametrize(
    "target",
    [
        "/repom.sqlite3",
        "/repom:memory:.sqlite3",
        "/repom.sqlite3?note=:memory:",
        "/file:real.db?uri=true",
        "/file:real.db#:memory:?uri=true",
        "/file:real.db?mode=ro&uri=true",
        "/file:real.db?mode=memory&mode=ro&uri=true",
    ],
    ids=["file", "memory-in-name", "memory-in-query", "uri", "uri-fragment", "uri-ro", "uri-repeat"],
)
def test_engine_kwargs_for_sqlite_file_urls_use_pool_options(driver, target):
    url = f"{driver}://{target}"
    config = RepomConfig(exec_env="dev")
    config.db_pool_size = 5
    config.db_max_overflow = 7
    config.db_pool_timeout = 15

    kwargs = config.engine_kwargs_for_url(url)

    assert "poolclass" not in kwargs
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 7
    assert kwargs["pool_timeout"] == 15
    engine = _create_engine_for_url(url, kwargs)
    engine.dispose()
