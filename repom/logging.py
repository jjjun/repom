"""
ロギングユーティリティ（ハイブリッドアプローチ）

repom は以下の優先順位でログ設定を行います:
1. アプリ側の logging.basicConfig() または dictConfig()（最優先）
2. repom のデフォルト設定（config.log_file_path を使用）
"""

from typing import Optional
import logging

from basekit.logging import (
    DateNamedDailyFileHandler,
    configure_default_logging,
    configure_sqlalchemy_logging,
    make_timed_rotating_handler,
)

_logger_initialized = False
_sqlalchemy_logging_initialized = False

_PACKAGE_LOGGER_NAME = "repom"


def get_logger(name: str) -> logging.Logger:
    """
    repom 用のロガーを取得します。取得時に handler は設定しません。

    name が既に "repom" または "repom." で始まる場合（呼び出し側が
    __name__ を渡す通常のケース）は、二重に "repom." を付けない。
    """
    if name == _PACKAGE_LOGGER_NAME or name.startswith(f"{_PACKAGE_LOGGER_NAME}."):
        logger = logging.getLogger(name)
    else:
        logger = logging.getLogger(f"{_PACKAGE_LOGGER_NAME}.{name}")

    return logger


def ensure_logging_configured() -> None:
    """Configure repom's default and SQLAlchemy logging once."""
    global _logger_initialized

    if not _logger_initialized:
        _logger_initialized = True

        from repom.config import config

        configure_default_logging("repom", config.log_file_path, config.log_level)
        _setup_sqlalchemy_logging()


def _setup_sqlalchemy_logging():
    """SQLAlchemy のクエリログを設定時に一度だけ構成する。"""
    global _sqlalchemy_logging_initialized

    if _sqlalchemy_logging_initialized:
        return

    _sqlalchemy_logging_initialized = True

    from repom.config import config

    apply_sqlalchemy_echo_state(
        enabled=config.enable_sqlalchemy_echo,
        echo_level=config.sqlalchemy_echo_level,
        log_file_path=config.log_file_path,
    )


def apply_sqlalchemy_echo_state(
    *,
    enabled: bool,
    echo_level: str = "INFO",
    log_file_path: Optional[str] = None,
) -> None:
    """SQLAlchemy echo 設定をランタイムで即時反映する（idempotent）。

    ``RepomConfig.enable_sqlalchemy_echo`` / ``sqlalchemy_echo_level`` の
    setter から呼ばれ、import 後に config を切り替えた場合でも次に実行される
    クエリから即座に反映される。有効化時は basekit の
    configure_sqlalchemy_logging に設定を委譲し、無効化時は
    "sqlalchemy.engine.Engine" ロガーのレベルを WARNING に戻してログを止める。
    """
    if not enabled:
        logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
        return

    configure_sqlalchemy_logging(
        enabled=True,
        echo_level=echo_level,
        log_file_path=log_file_path,
    )


__all__ = [
    "get_logger",
    "ensure_logging_configured",
    "apply_sqlalchemy_echo_state",
    "make_timed_rotating_handler",
    "DateNamedDailyFileHandler",
]
