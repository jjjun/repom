"""
repom/logging.py のテスト（ハイブリッドアプローチ）
"""

import logging
import pytest
from pathlib import Path
from unittest.mock import patch

from repom.logging import get_logger


class TestGetLogger:
    """get_logger() の動作確認（ハイブリッドアプローチ）"""

    def test_get_logger_returns_logger(self):
        """ロガーが正しく取得できる"""
        logger = get_logger('test')
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'repom.test'

    def test_get_logger_with_basicConfig(self, tmp_path, monkeypatch):
        """
        アプリ側で logging.basicConfig() を呼んだ場合、
        repom のデフォルト設定はスキップされる
        """
        # basicConfig() を先に呼ぶ（ハンドラーを追加）
        app_log_file = tmp_path / "app.log"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(name)s - %(message)s',
            handlers=[logging.FileHandler(app_log_file)]
        )

        # repom のルートロガーにハンドラーが追加されているか確認
        repom_root_logger = logging.getLogger('repom')
        assert len(repom_root_logger.handlers) > 0  # basicConfig() でハンドラーが追加される

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
        log_file = tmp_path / "test.log"
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))

        logger = get_logger('test')

        # repom のルートロガーにハンドラーが追加されているか確認
        assert len(repom_root_logger.handlers) == 2  # FileHandler + ConsoleHandler

        # ログファイルが作成されているか確認
        logger.debug("Test message")
        assert log_file.exists()

        # ログファイルの内容を確認
        content = log_file.read_text(encoding='utf-8')
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

        logger = get_logger('test')

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
        log_file = tmp_path / "test.log"
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))

        # 1回目の呼び出し
        logger1 = get_logger('test1')
        handler_count_1 = len(repom_root_logger.handlers)

        # 2回目の呼び出し
        logger2 = get_logger('test2')
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
        log_file = tmp_path / "logs" / "subdir" / "test.log"
        assert not log_file.parent.exists()

        # config.log_file_path をモック（monkeypatch を使用）
        from repom.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))

        logger = get_logger('test')
        logger.debug("Test message")

        # ログディレクトリが作成されたことを確認
        assert log_file.parent.exists()
        assert log_file.exists()
