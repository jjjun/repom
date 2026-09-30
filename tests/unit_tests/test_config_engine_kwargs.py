"""RepomConfig engine settings for supported database URL shapes."""

import pytest
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
