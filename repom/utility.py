import os
import inflect
import unicodedata
from typing import Optional, List

# Import generic discovery helpers from repom._
from repom._.discovery import (
    normalize_paths,
    DiscoveryFailure,
    DiscoveryError,
    validate_package_security,
    import_packages,
    import_from_directory,
    import_package_directory,
    import_from_packages,
    DEFAULT_EXCLUDED_DIRS as _BASE_EXCLUDED_DIRS,
)

"""
inflect
英語の単語の複数形、単数形、序数、冠詞などを生成するためのPythonライブラリです。
このライブラリを使用すると、英語の文法規則に基づいて単語の形態を変化させることができます。
主な機能
複数形の生成: 単語の複数形を生成します。
単数形の生成: 単語の単数形を生成します。
序数の生成: 数字を序数(1st, 2nd, 3rd など)に変換します。
冠詞の追加: 単語に適切な冠詞(a, an, the)を追加します。
"""

# repom 固有の除外ディレクトリ（モデル用途に特化）
DEFAULT_EXCLUDED_DIRS = _BASE_EXCLUDED_DIRS | {'base', 'mixin', 'validators', 'utils', 'helpers'}

__all__ = [
    # Discovery helpers (re-exported)
    'normalize_paths',
    'DiscoveryFailure',
    'DiscoveryError',
    'validate_package_security',
    'import_packages',
    'import_from_directory',
    'import_package_directory',
    'import_from_packages',
    'DEFAULT_EXCLUDED_DIRS',
    # Utility functions
    'get_plural_tablename',
    'normalize_text',
    # repom specific
    'load_models',
]


def get_plural_tablename(file_path: str) -> str:
    """
    ファイル名から拡張子を除去し、複数形に変換してテーブル名を取得する関数。

    Args:
        file_path (str): ファイルのパス

    Returns:
        str: 複数形に変換されたテーブル名
    """
    # ファイル名を取得し、拡張子を除去
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # inflect エンジンを初期化
    p = inflect.engine()

    # ファイル名を複数形に変換
    table_name = p.plural(file_name)

    return table_name


def normalize_text(s: str) -> str:
    """
    テキストの正規化（全角・半角・空白・小文字化）
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "").replace("　", "")
    return s.lower()


def load_models(context: Optional[str] = None) -> None:
    """Import all application models so SQLAlchemy can discover metadata.

    This function imports models based on config.model_locations setting.
    If model_locations is not set, it falls back to importing repom.examples.models.

    Args:
        context: Execution context for logging (e.g., "db_create", "db_delete", "alembic_migration")

    Usage:
        from repom.utility import load_models
        load_models(context="db_create")  # Import with context info

    Note:
        This function is typically called by:
        - Alembic migrations (alembic/env.py)
        - Database scripts (db_create.py, db_delete.py, etc.)
        - Test fixtures (tests/conftest.py)
        
        Uses import_from_packages() from discovery module with SQLAlchemy's
        configure_mappers() as post_import_hook.
    """
    from repom.config import config
    from repom.logging import get_logger
    from sqlalchemy.orm import configure_mappers

    logger = get_logger(__name__)
    context_prefix = f"[{context}] " if context else ""

    logger.debug(f"{context_prefix}Starting model loading...")

    if config.model_locations:
        # Use generic discovery infrastructure with SQLAlchemy hook
        import_from_packages(
            package_names=config.model_locations,
            excluded_dirs=config.model_excluded_dirs,
            allowed_prefixes=config.allowed_package_prefixes,
            fail_on_error=config.model_import_strict,
            post_import_hook=configure_mappers
        )
    else:
        # デフォルト動作（後方互換性）
        try:
            from repom.examples import models  # noqa: F401  # pylint: disable=unused-import
        except ImportError:
            logger.warning(f"{context_prefix}No model locations configured and repom.examples.models not found.")

    # Log loaded models
    from repom.models.base_model import Base
    try:
        table_names = sorted(Base.metadata.tables.keys())
        logger.debug(f"{context_prefix}Loaded {len(table_names)} models: {', '.join(table_names)}")
    except Exception as e:
        logger.warning(f"{context_prefix}Could not retrieve model list: {e}")
