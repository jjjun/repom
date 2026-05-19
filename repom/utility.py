import os
import inflect
import unicodedata
from typing import Optional

# Import generic discovery helpers from basekit.
from basekit.discovery import (
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
Python


: 
: 
: (1st, 2nd, 3rd )
: (a, an, the)
"""

# repom 
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
    

    Args:
        file_path (str): 

    Returns:
        str: 
    """
    # 
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # inflect 
    p = inflect.engine()

    # 
    table_name = p.plural(file_name)

    return table_name


def normalize_text(s: str) -> str:
    """
    
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "").replace("", "")
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
        logger.info(f"{context_prefix}No model locations configured. Skipping model import.")

    # Log loaded models
    from repom.models.base_model import Base
    try:
        table_names = sorted(Base.metadata.tables.keys())
        logger.debug(f"{context_prefix}Loaded {len(table_names)} models: {', '.join(table_names)}")
    except Exception as e:
        logger.warning(f"{context_prefix}Could not retrieve model list: {e}")


