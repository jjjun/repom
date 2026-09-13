"""Tests documenting SQLAlchemy engine echo/log behaviour and repom's mitigation.

repom#141: the ``sqlalchemy_echo_level`` docstring used to claim that ``INFO``
only emits SQL statement text. In SQLAlchemy 2.x, the engine logger at
``INFO`` also emits the bound parameter tuple for every statement. These
tests pin down the real behaviour and verify that
``config.sqlalchemy_hide_parameters`` (default ``True``) suppresses it.
"""

import logging

from sqlalchemy import create_engine, text

from repom.config import RepomConfig


SENTINEL = "sentinel-bound-parameter-value"


def test_echo_info_logs_bound_parameters(caplog):
    """SQLAlchemy's INFO engine log includes bound parameter values."""
    engine = create_engine("sqlite:///:memory:", echo=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (v TEXT)"))

        with caplog.at_level(logging.INFO, logger="sqlalchemy.engine.Engine"):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": SENTINEL})

        assert SENTINEL in caplog.text
    finally:
        engine.dispose()


def test_hide_parameters_suppresses_values(caplog):
    """``hide_parameters=True`` keeps the statement but drops bound values."""
    engine = create_engine("sqlite:///:memory:", echo=True, hide_parameters=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (v TEXT)"))

        with caplog.at_level(logging.INFO, logger="sqlalchemy.engine.Engine"):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": SENTINEL})

        assert SENTINEL not in caplog.text
        assert "INSERT INTO t" in caplog.text
    finally:
        engine.dispose()


class TestSqlalchemyHideParametersConfig:
    """``RepomConfig.sqlalchemy_hide_parameters`` defaults and wiring."""

    def test_defaults_to_true(self):
        config = RepomConfig()
        assert config.sqlalchemy_hide_parameters is True

    def test_is_settable(self):
        config = RepomConfig()
        config.sqlalchemy_hide_parameters = False
        assert config.sqlalchemy_hide_parameters is False

    def test_postgres_engine_kwargs_reflect_setting(self):
        config = RepomConfig()
        config.db_type = "postgres"
        config.sqlalchemy_hide_parameters = False

        assert config.engine_kwargs["hide_parameters"] is False

    def test_sqlite_file_engine_kwargs_reflect_setting(self):
        config = RepomConfig()
        config.db_type = "sqlite"
        config.root_path = "/tmp/repom"
        config.sqlite.use_in_memory_for_tests = False
        config.init()

        assert config.engine_kwargs["hide_parameters"] is True

    def test_sqlite_memory_engine_kwargs_reflect_setting(self):
        config = RepomConfig()
        config.db_type = "sqlite"
        config.root_path = "/tmp/repom"
        config._db_url = "sqlite:///:memory:"
        config.sqlalchemy_hide_parameters = False

        assert config.engine_kwargs["hide_parameters"] is False
