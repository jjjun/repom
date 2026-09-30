"""Tests for repom's SQLAlchemy echo logging configuration."""

import logging

from sqlalchemy import create_engine, text

from repom.config import RepomConfig


class TestEnableSqlalchemyEchoRuntimeToggle:
    """config.enable_sqlalchemy_echo を import 後に切り替えた場合の即時反映を確認する（repom#162）。

    以前は _setup_sqlalchemy_logging() が最初の get_logger() 呼び出し時
    （通常 repom.database の import 時）に一度だけ実行され、その時点の
    config.enable_sqlalchemy_echo の値で "sqlalchemy.engine.Engine" ロガーの
    状態が固定されていたため、import 後に切り替えても反映されなかった。
    """

    def test_toggle_after_import_enables_and_disables_engine_logging(self, tmp_path, caplog):
        import repom.database  # noqa: F401 - repom.database が import 済みであることの前提

        test_config = RepomConfig(exec_env="test")
        test_config.log_path = str(tmp_path)
        test_config.log_file = "sqlalchemy_echo_toggle"

        sqlalchemy_logger = logging.getLogger("sqlalchemy.engine.Engine")
        original_level = sqlalchemy_logger.level
        original_handlers = list(sqlalchemy_logger.handlers)

        engine = create_engine("sqlite:///:memory:")
        try:
            test_config.enable_sqlalchemy_echo = True

            caplog.clear()
            with caplog.at_level(logging.DEBUG):
                with engine.begin() as conn:
                    conn.execute(text("SELECT 1"))
            assert any(
                record.name == "sqlalchemy.engine.Engine" for record in caplog.records
            )

            test_config.enable_sqlalchemy_echo = False

            caplog.clear()
            with caplog.at_level(logging.DEBUG):
                with engine.begin() as conn:
                    conn.execute(text("SELECT 1"))
            assert not any(
                record.name == "sqlalchemy.engine.Engine" for record in caplog.records
            )
        finally:
            engine.dispose()
            for handler in sqlalchemy_logger.handlers[:]:
                if handler not in original_handlers:
                    handler.close()
                    sqlalchemy_logger.removeHandler(handler)
            sqlalchemy_logger.setLevel(original_level)


class TestSqlalchemyHideParametersConfig:
    """``RepomConfig.sqlalchemy_hide_parameters`` defaults and wiring."""

    def test_defaults_to_true(self):
        config = RepomConfig()
        assert config.sqlalchemy_hide_parameters is True

    def test_is_settable(self):
        config = RepomConfig()
        config.sqlalchemy_hide_parameters = False
        assert config.sqlalchemy_hide_parameters is False
