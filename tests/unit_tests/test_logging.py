"""
repom/logging.py のテスト（ハイブリッドアプローチ）
"""

import logging
from datetime import date
from pathlib import Path
import pytest

from repom.config import RepomConfig
from repom.logging import get_logger


@pytest.fixture(autouse=True)
def reset_logging_state():
    import repom.logging as logging_module

    logging_module._logger_initialized = False
    logging_module._sqlalchemy_logging_initialized = False
    repom_root_logger = logging.getLogger('repom')
    root_logger = logging.getLogger()
    original_root_handlers = list(root_logger.handlers)

    for handler in original_root_handlers:
        root_logger.removeHandler(handler)
    for handler in repom_root_logger.handlers[:]:
        handler.close()
        repom_root_logger.removeHandler(handler)

    yield

    logging_module._logger_initialized = False
    logging_module._sqlalchemy_logging_initialized = False
    for handler in repom_root_logger.handlers[:]:
        handler.close()
        repom_root_logger.removeHandler(handler)
    for handler in root_logger.handlers[:]:
        if handler not in original_root_handlers:
            handler.close()
            root_logger.removeHandler(handler)
    for handler in original_root_handlers:
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)


class TestGetLogger:
    """get_logger() の動作確認（ハイブリッドアプローチ）"""

    def test_get_logger_returns_logger(self):
        """ロガーが正しく取得できる"""
        logger = get_logger('test')
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'repom.test'

    def test_get_logger_with_basicConfig(self, tmp_path, monkeypatch, request):
        """
        アプリ側で logging.basicConfig() を呼んだ場合、
        repom のデフォルト設定はスキップされる
        """
        # basicConfig() を先に呼ぶ（ハンドラーを追加）
        app_log_file = tmp_path / "app.log"
        app_handler = logging.FileHandler(app_log_file)
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(name)s - %(message)s',
            handlers=[app_handler]
        )

        # root logger にハンドラーが追加されているか確認
        root_logger = logging.getLogger()
        repom_root_logger = logging.getLogger('repom')

        def cleanup_handler():
            root_logger.removeHandler(app_handler)
            app_handler.close()

        request.addfinalizer(cleanup_handler)
        assert len(root_logger.handlers) > 0

        # get_logger() を呼んでも、追加のハンドラーは追加されない
        logger = get_logger('test')
        assert logger.name == 'repom.test'

        # ハンドラー数が変わらないことを確認
        # （実際には root logger のハンドラーが継承される）
        initial_count = len(repom_root_logger.handlers)
        _ = get_logger('test2')
        assert len(repom_root_logger.handlers) == initial_count

    def test_default_logging_setup(self, tmp_path, monkeypatch):
        """
        ハンドラーがない場合、repom のデフォルト設定が適用される
        """
        repom_root_logger = logging.getLogger('repom')

        # config.log_file_path をモック（monkeypatch を使用）
        log_file = tmp_path / "test"
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))

        logger = get_logger('test')

        # repom のルートロガーにハンドラーが追加されているか確認
        assert len(repom_root_logger.handlers) == 2  # FileHandler + ConsoleHandler

        # ログファイルが作成されているか確認
        logger.debug("Test message")
        active_log_file = tmp_path / f"test_{date.today().isoformat()}.log"
        assert active_log_file.exists()

        # ログファイルの内容を確認
        content = active_log_file.read_text(encoding='utf-8')
        assert "Test message" in content
        assert "repom.test" in content

    def test_log_file_path_none(self, monkeypatch):
        """
        config.log_file_path が None の場合、ハンドラーは追加されない
        """
        repom_root_logger = logging.getLogger('repom')

        # config.log_file_path を None にモック（monkeypatch を使用）
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: None))

        get_logger('test')

        # ハンドラーが追加されていないことを確認
        assert len(repom_root_logger.handlers) == 0

    def test_logger_initialization_once(self, tmp_path, monkeypatch):
        """
        get_logger() を複数回呼んでも、ハンドラーは1回だけ追加される
        """
        repom_root_logger = logging.getLogger('repom')

        # config.log_file_path をモック（monkeypatch を使用）
        log_file = tmp_path / "test"
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))

        # 1回目の呼び出し
        get_logger('test1')
        handler_count_1 = len(repom_root_logger.handlers)

        # 2回目の呼び出し
        get_logger('test2')
        handler_count_2 = len(repom_root_logger.handlers)

        # ハンドラー数が変わらないことを確認
        assert handler_count_1 == handler_count_2 == 2  # FileHandler + ConsoleHandler

    def test_log_directory_creation(self, tmp_path, monkeypatch):
        """
        ログディレクトリが存在しない場合、自動作成される
        """
        # 存在しないディレクトリを指定
        log_file = tmp_path / "logs" / "subdir" / "test"
        assert not log_file.parent.exists()

        # config.log_file_path をモック（monkeypatch を使用）
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))

        logger = get_logger('test')
        logger.debug("Test message")

        # ログディレクトリが作成されたことを確認
        assert log_file.parent.exists()
        assert (log_file.parent / f"test_{date.today().isoformat()}.log").exists()


class TestGetLoggerModuleNaming:
    """__name__ を渡す通常の呼び出しで "repom." が二重に付かないことを確認する（repom#162）。"""

    def test_get_logger_does_not_double_prefix_repom_names(self):
        """name が既に "repom" / "repom." の場合はそのまま使われる。"""
        assert get_logger('repom').name == 'repom'
        assert get_logger('repom.database').name == 'repom.database'

    def test_database_module_logger_matches_getLogger(self):
        """repom/database.py の logger は logging.getLogger("repom.database") と同一。"""
        import repom.database as database_module

        assert database_module.logger.name == 'repom.database'
        assert database_module.logger is logging.getLogger('repom.database')

    def test_setting_repom_database_level_to_critical_suppresses_records(self, caplog):
        """logging.getLogger("repom.database") への level 設定が実際に効く。"""
        import repom.database as database_module

        target_logger = logging.getLogger('repom.database')
        original_level = target_logger.level
        try:
            with caplog.at_level(logging.DEBUG):
                database_module.logger.info('visible before CRITICAL is set')
            assert 'visible before CRITICAL is set' in caplog.text
            caplog.clear()

            target_logger.setLevel(logging.CRITICAL)
            with caplog.at_level(logging.DEBUG):
                database_module.logger.info('suppressed by repom.database level')
            assert 'suppressed by repom.database level' not in caplog.text
        finally:
            target_logger.setLevel(original_level)


def test_prod_logging_uses_info_level_for_file_handler(tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    config = RepomConfig(exec_env="prod")
    config.log_path = str(tmp_path)
    config.log_file = "prod"
    monkeypatch.setattr("repom.config.config", config)

    logger = get_logger("prod_level")
    logger.debug("debug message")
    logger.info("info message")

    file_handler = next(
        handler
        for handler in logging.getLogger("repom").handlers
        if isinstance(handler, logging.FileHandler)
    )
    file_handler.flush()

    assert file_handler.level == logging.INFO
    content = Path(file_handler.baseFilename).read_text(encoding="utf-8")
    assert "debug message" not in content
    assert "info message" in content


def test_non_prod_logging_keeps_debug_file_level(tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    config = RepomConfig(exec_env="dev")
    config.log_path = str(tmp_path)
    config.log_file = "dev"
    monkeypatch.setattr("repom.config.config", config)

    logger = get_logger("dev_level")
    logger.debug("debug message")

    file_handler = next(
        handler
        for handler in logging.getLogger("repom").handlers
        if isinstance(handler, logging.FileHandler)
    )
    console_handler = next(
        handler
        for handler in logging.getLogger("repom").handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    )
    file_handler.flush()

    assert file_handler.level == logging.DEBUG
    assert console_handler.level == logging.INFO
    assert "debug message" in Path(file_handler.baseFilename).read_text(encoding="utf-8")
