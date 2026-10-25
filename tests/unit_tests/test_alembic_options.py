"""Unit tests for the version table option helper shared by env.py and setup."""

from alembic.config import Config
import pytest

from repom.alembic.options import resolve_version_table_options


def _config(**options):
    config = Config()
    for name, value in options.items():
        config.set_main_option(name, value)
    return config


@pytest.mark.parametrize("blank", [None, "", "   ", "\t"])
def test_blank_or_absent_options_use_defaults(blank):
    options = {} if blank is None else {
        "version_table": blank,
        "version_table_schema": blank,
    }

    assert resolve_version_table_options(_config(**options)) == (
        "alembic_version",
        None,
    )


def test_configured_options_are_stripped():
    config = _config(
        version_table="  alembic_version_app  ",
        version_table_schema="  migration_app  ",
    )

    assert resolve_version_table_options(config) == (
        "alembic_version_app",
        "migration_app",
    )
