"""
ロギングユーティリティ（ハイブリッドアプローチ）

repom は以下の優先順位でログ設定を行います:
1. アプリ側の logging.basicConfig() または dictConfig()（最優先）
2. repom のデフォルト設定（config.log_file_path を使用）
"""

import logging

from basekit.logging import (
    DateNamedDailyFileHandler,
    configure_default_logging,
    configure_sqlalchemy_logging,
    make_timed_rotating_handler,
)

_logger_initialized = False
_sqlalchemy_logging_initialized = False


def get_logger(name: str) -> logging.Logger:
    """
    repom 用のロガーを取得（ハイブリッドアプローチ）

    デフォルト動作:
        - config.log_file_path に基づいてログを設定
        - repom のルートロガーにハンドラーがない場合のみ設定
    """
    global _logger_initialized

    logger = logging.getLogger(f"repom.{name}")

    if not _logger_initialized:
        _logger_initialized = True

        from repom.config import config

        configure_default_logging("repom", config.log_file_path)
        _setup_sqlalchemy_logging()

    return logger


def _setup_sqlalchemy_logging():
    """SQLAlchemy のクエリログを設定する。"""
    global _sqlalchemy_logging_initialized

    if _sqlalchemy_logging_initialized:
        return

    _sqlalchemy_logging_initialized = True

    from repom.config import config

    configure_sqlalchemy_logging(
        enabled=config.enable_sqlalchemy_echo,
        echo_level=config.sqlalchemy_echo_level,
        log_file_path=config.log_file_path,
    )


__all__ = [
    "get_logger",
    "_setup_sqlalchemy_logging",
    "make_timed_rotating_handler",
    "DateNamedDailyFileHandler",
]
