"""
repom/logging.py のテスト（ハイブリッドアプローチ）
"""

import logging
from datetime import date
import pytest

from repom.logging import DateNamedDailyFileHandler, get_logger, make_timed_rotating_handler


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
        # repom/logging.py の _logger_initialized をリセット
        import repom.logging
        repom.logging._logger_initialized = False

        # logging の状態をリセット
        logging.shutdown()

        # repom のルートロガーをリセット
        repom_root_logger = logging.getLogger('repom')
        for handler in repom_root_logger.handlers[:]:
            repom_root_logger.removeHandler(handler)

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
        # repom/logging.py の _logger_initialized をリセット
        import repom.logging
        repom.logging._logger_initialized = False

        # logging の状態をリセット
        logging.shutdown()

        # repom のルートロガーをリセット
        repom_root_logger = logging.getLogger('repom')
        for handler in repom_root_logger.handlers[:]:
            repom_root_logger.removeHandler(handler)

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
        # repom/logging.py の _logger_initialized をリセット
        import repom.logging
        repom.logging._logger_initialized = False

        # logging の状態をリセット
        logging.shutdown()

        # repom のルートロガーをリセット
        repom_root_logger = logging.getLogger('repom')
        for handler in repom_root_logger.handlers[:]:
            repom_root_logger.removeHandler(handler)

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
        # repom/logging.py の _logger_initialized をリセット
        import repom.logging
        repom.logging._logger_initialized = False

        # logging の状態をリセット
        logging.shutdown()

        # repom のルートロガーをリセット
        repom_root_logger = logging.getLogger('repom')
        for handler in repom_root_logger.handlers[:]:
            repom_root_logger.removeHandler(handler)

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


class TestDateNamedDailyFileHandler:
    """日付付きアクティブログファイル handler の動作確認。"""

    def test_make_handler_writes_to_dated_active_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            DateNamedDailyFileHandler,
            '_today',
            lambda self: date(2026, 5, 5),
        )

        handler = make_timed_rotating_handler(str(tmp_path / 'main'))
        logger = logging.getLogger('repom.handler_test')
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info("active file message")
        handler.flush()
        handler.close()

        active_file = tmp_path / 'main_2026-05-05.log'
        assert active_file.exists()
        assert not (tmp_path / 'main').exists()
        assert "active file message" in active_file.read_text(encoding='utf-8')

    def test_handler_switches_file_when_date_changes(self, tmp_path, monkeypatch):
        current = date(2026, 5, 5)
        monkeypatch.setattr(
            DateNamedDailyFileHandler,
            '_today',
            lambda self: current,
        )

        handler = make_timed_rotating_handler(str(tmp_path / 'main'))
        logger = logging.getLogger('repom.handler_switch_test')
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info("first day")
        current = date(2026, 5, 6)
        logger.info("second day")
        handler.flush()
        handler.close()

        first_file = tmp_path / 'main_2026-05-05.log'
        second_file = tmp_path / 'main_2026-05-06.log'
        assert "first day" in first_file.read_text(encoding='utf-8')
        assert "second day" in second_file.read_text(encoding='utf-8')

    def test_handler_deletes_old_logs_by_backup_count(self, tmp_path, monkeypatch):
        for day in range(1, 5):
            (tmp_path / f"main_2026-05-0{day}.log").write_text(
                f"day {day}",
                encoding='utf-8',
            )

        monkeypatch.setattr(
            DateNamedDailyFileHandler,
            '_today',
            lambda self: date(2026, 5, 5),
        )

        handler = make_timed_rotating_handler(str(tmp_path / 'main'), backup_count=3)
        handler.close()

        assert not (tmp_path / 'main_2026-05-01.log').exists()
        assert not (tmp_path / 'main_2026-05-02.log').exists()
        assert (tmp_path / 'main_2026-05-03.log').exists()
        assert (tmp_path / 'main_2026-05-04.log').exists()
        assert (tmp_path / 'main_2026-05-05.log').exists()
