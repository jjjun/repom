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
"""

import logging
from pathlib import Path
from typing import Optional

_logger_initialized = False
_sqlalchemy_logging_initialized = False


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
        → config.log_file_path + コンソールに出力

        # アプリ側で制御（優先される）
        import logging
        logging.basicConfig(handlers=[...])
        → アプリ側の設定に従う

        # アプリ側で設定なし（デフォルト動作）
        from repom.logging import get_logger
        logger = get_logger(__name__)
        → config.log_file_path + コンソールに出力

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
                # ログディレクトリを作成
                log_path = Path(config.log_file_path)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                # ログレベルを設定
                repom_root_logger.setLevel(logging.DEBUG)

                # FileHandler を追加
                file_handler = logging.FileHandler(config.log_file_path, encoding='utf-8')
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
        file_handler = logging.FileHandler(config.log_file_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - sqlalchemy.engine.Engine - %(levelname)s - %(message)s')
        )
        sqlalchemy_logger.addHandler(file_handler)


__all__ = ['get_logger', '_setup_sqlalchemy_logging']
