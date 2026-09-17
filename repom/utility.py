import os
import logging
import time
import unicodedata
from typing import List, Optional

import inflect

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

# repom-specific excluded directories (model discovery only)
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
    Derive a table name from a file name by pluralizing it.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: The pluralized table name.
    """
    # Strip the extension, keeping only the file's base name.
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # Initialize the inflect engine.
    p = inflect.engine()

    # Pluralize the file name.
    table_name = p.plural(file_name)

    return table_name


def normalize_text(s: str) -> str:
    """
    Normalize text (full-width/half-width, whitespace, lowercase).
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "")
    return s.lower()


def load_models(
    context: Optional[str] = None, *, strict: Optional[bool] = None
) -> List[DiscoveryFailure]:
    """Import all application models so SQLAlchemy can discover metadata.

    This function imports models based on config.model_locations setting.
    If model_locations is not set, no model modules are imported and a message
    is logged noting that model import was skipped.

    Args:
        context: Execution context for logging (e.g., "db_create", "db_delete", "alembic_migration")
        strict: When True, raise DiscoveryError if any model module failed to
            import, overriding config.model_import_strict for this call. When
            None (default), config.model_import_strict decides. Callers whose
            downstream step is destructive when run against partial metadata
            (alembic autogenerate, db_create) pass strict=True explicitly so
            they refuse regardless of the configured default.

    Returns:
        The list of DiscoveryFailure entries for model modules that failed to
        import. Empty when model_locations is unset or every module imported
        successfully.

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

        Every import failure is logged at ERROR with the module name and the
        exception, regardless of model_import_strict, so a partial load is
        never silent even when the caller chooses to proceed.

        Set the ``models.detail`` child logger to DEBUG to include
        the full table-name list in logs.
    """
    from repom.config import config
    from repom.logging import get_logger
    from sqlalchemy.orm import configure_mappers

    logger = get_logger(__name__)
    detail_logger = logger.getChild('models.detail')
    if detail_logger.level == logging.NOTSET:
        detail_logger.setLevel(logging.INFO)
    context_prefix = f"[{context}] " if context else ""
    started_at = time.perf_counter()

    failures: List[DiscoveryFailure] = []
    if config.model_locations:
        # Use generic discovery infrastructure with SQLAlchemy hook.
        # fail_on_error is always False here so failures are always captured
        # and logged before the strict/raise decision below.
        failures = import_from_packages(
            package_names=config.model_locations,
            excluded_dirs=config.model_excluded_dirs,
            allowed_prefixes=config.allowed_package_prefixes,
            fail_on_error=False,
            post_import_hook=configure_mappers
        )
        for failure in failures:
            logger.error(
                "%sFailed to import model module '%s': %s: %s",
                context_prefix, failure.target, failure.exception_type, failure.message
            )
    else:
        logger.info(f"{context_prefix}No model locations configured. Skipping model import.")

    # Log loaded models
    from repom.models.base_model import Base
    try:
        table_names = sorted(Base.metadata.tables.keys())
        logger.debug(
            "%sLoaded %d models in %.2fs",
            context_prefix,
            len(table_names),
            time.perf_counter() - started_at,
        )
        if detail_logger.isEnabledFor(logging.DEBUG):
            detail_logger.debug(
                "%sLoaded models: %s", context_prefix, ', '.join(table_names)
            )
    except Exception as e:
        logger.warning(f"{context_prefix}Could not retrieve model list: {e}")

    effective_strict = config.model_import_strict if strict is None else strict
    if failures and effective_strict:
        raise DiscoveryError(failures)

    return failures


