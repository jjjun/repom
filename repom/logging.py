"""
ロギングユーティリティ（ハイブリッドアプローチ）

repom は以下の優先順位でログ設定を行います:
1. アプリ側の logging.basicConfig() または dictConfig()（最優先）
2. repom のデフォルト設定（config.log_file_path を使用）

CLI ツール実行時:
    repom のデフォルト設定が適用されます。
    
アプリケーション実行時:
    アプリ側で logging.basicConfig() を呼べば、そちらが優先されます。
    呼ばなければ、repom のデフォルト設定が使われます。

ログファイル命名規則:
    <区分>_<YYYY-MM-DD>.log
    例: main_2026-05-05.log / test_2026-05-05.log
    日付が変わると自動ローテーション（デフォルト 30 日分保持）
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

_logger_initialized = False
_sqlalchemy_logging_initialized = False


def _make_timed_rotating_handler(base_path: str, backup_count: int = 30) -> TimedRotatingFileHandler:
    """``<base_path>_<YYYY-MM-DD>.log`` 形式で日次ローテーションするハンドラーを作成

    Args:
        base_path: ログファイルのベースパス（拡張子・日付なし）
        backup_count: 保持する世代数（デフォルト: 30日分）

    Returns:
        TimedRotatingFileHandler
    """
    log_path = Path(base_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        str(log_path),
        when='midnight',
        backupCount=backup_count,
        encoding='utf-8',
    )
    # ローテーション後のファイル名: <base>_<YYYY-MM-DD>.log
    handler.suffix = '_%Y-%m-%d.log'
    # アクティブなファイル名も同形式にする
    # デフォルトは <base>.YYYY-MM-DD になるが、namer で <base>_<YYYY-MM-DD>.log に変換
    import re
    handler.extMatch = re.compile(r'_\d{4}-\d{2}-\d{2}\.log$')

    def namer(default_name: str) -> str:
        # default_name 例: /path/main.2026-05-04
        # → /path/main_2026-05-04.log
        base, _, date_part = default_name.rpartition('.')
        return f"{base}_{date_part}.log"

    handler.namer = namer

    return handler


def get_logger(name: str) -> logging.Logger:
    """
    repom 用のロガーを取得（ハイブリッドアプローチ）

    デフォルト動作:
        - config.log_file_path に基づいてログを設定
        - repom のルートロガーにハンドラーがない場合のみ設定

    アプリ側で制御:
        - logging.basicConfig() を呼べば、そちらが優先される
        - repom のデフォルト設定はスキップされる

    Args:
        name: ロガー名（通常は __name__）

    Returns:
        logging.Logger: 設定済みロガー

    Examples:
        # CLI ツール（repom 単体）
        poetry run db_create
        → <区分>_<YYYY-MM-DD>.log + コンソールに出力

        # アプリ側で制御（優先される）
        import logging
        logging.basicConfig(handlers=[...])
        → アプリ側の設定に従う

        # アプリ側で設定なし（デフォルト動作）
        from repom.logging import get_logger
        logger = get_logger(__name__)
        → <区分>_<YYYY-MM-DD>.log + コンソールに出力

    Note:
        最初の呼び出し時に、repom のルートロガーにハンドラーがない場合のみ、
        config.log_file_path に基づいてデフォルト設定を追加します。
    """
    global _logger_initialized

    logger = logging.getLogger(f'repom.{name}')

    # 最初の呼び出し時のみ設定
    if not _logger_initialized:
        _logger_initialized = True

        # repom のルートロガーを取得
        repom_root_logger = logging.getLogger('repom')

        # ルートロガーにハンドラーがない場合のみ、デフォルト設定を追加
        if not repom_root_logger.handlers:
            from repom.config import config

            if config.log_file_path:
                # ログレベルを設定
                repom_root_logger.setLevel(logging.DEBUG)

                # 日次ローテーションファイルハンドラーを追加
                file_handler = _make_timed_rotating_handler(config.log_file_path)
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                )
                repom_root_logger.addHandler(file_handler)

                # コンソール出力を追加（CLI ツール用）
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(
                    logging.Formatter('%(levelname)s: %(message)s')
                )
                repom_root_logger.addHandler(console_handler)

        # SQLAlchemy クエリログの設定
        _setup_sqlalchemy_logging()

    return logger


def _setup_sqlalchemy_logging():
    """SQLAlchemy のクエリログを設定

    config.enable_sqlalchemy_echo が True の場合に、
    SQLAlchemy のクエリを repom のログシステムに統合します。

    設定内容:
        - INFO: SQL文のみを出力（N+1 問題の調査に最適）
        - DEBUG: SQL文 + パラメータ + 実行結果の詳細

    Note:
        この関数は get_logger() の初回呼び出し時に自動的に実行されます。
        手動で呼び出す必要はありません。
    """
    global _sqlalchemy_logging_initialized

    # 既に初期化済みの場合はスキップ
    if _sqlalchemy_logging_initialized:
        return

    _sqlalchemy_logging_initialized = True

    from repom.config import config

    # config.enable_sqlalchemy_echo が False の場合は何もしない
    if not config.enable_sqlalchemy_echo:
        return

    # SQLAlchemy のロガーを取得（Engine レベルで取得）
    sqlalchemy_logger = logging.getLogger('sqlalchemy.engine.Engine')

    # レベルを設定
    level_map = {
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG
    }
    log_level = level_map.get(config.sqlalchemy_echo_level, logging.INFO)
    sqlalchemy_logger.setLevel(log_level)

    # 既にハンドラーが設定されている場合はスキップ
    if sqlalchemy_logger.handlers:
        return

    # コンソールハンドラーを追加（開発時に見やすいように）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter('🔍 SQL: %(message)s')
    )
    sqlalchemy_logger.addHandler(console_handler)

    # ファイルハンドラーを追加（ログファイルが設定されている場合）
    if config.log_file_path:
        file_handler = _make_timed_rotating_handler(config.log_file_path)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - sqlalchemy.engine.Engine - %(levelname)s - %(message)s')
        )
        sqlalchemy_logger.addHandler(file_handler)


__all__ = ['get_logger', '_setup_sqlalchemy_logging']

