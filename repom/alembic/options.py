"""Shared reading of Alembic version table options."""

from alembic.config import Config as AlembicConfig

DEFAULT_VERSION_TABLE = "alembic_version"


def resolve_version_table_options(
    config: AlembicConfig,
) -> tuple[str, str | None]:
    """Return ``(version_table, version_table_schema)`` from an Alembic config.

    ``get_main_option`` returns ``""`` for a present-but-empty option, so an
    empty or whitespace-only value is treated like an absent one: the table
    falls back to ``alembic_version`` and the schema to ``None``. env.py and
    ``AlembicSetup.from_ini`` both use this so they never disagree about
    which version table is in use.
    """
    version_table = (
        config.get_main_option("version_table") or ""
    ).strip() or DEFAULT_VERSION_TABLE
    version_table_schema = (
        config.get_main_option("version_table_schema") or ""
    ).strip() or None
    return version_table, version_table_schema
