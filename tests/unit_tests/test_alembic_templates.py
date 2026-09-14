"""Unit tests for AlembicTemplates.generate_alembic_ini input validation.

A newline in an interpolated value ends the current ini key and starts a
new one; the shared alembic/env.py trusts keys it reads from this file,
including pre_migration_hook, which resolves and calls a module:callable
target unconditionally. These tests confirm generate_alembic_ini rejects
values that could inject a key rather than silently writing them.
"""

import configparser

import pytest

from repom.alembic.templates import AlembicTemplates

INJECTION_PAYLOAD = "safe\npre_migration_hook = evil:run"


def _base_kwargs():
    return {
        "script_location": "alembic",
        "version_locations": "%(here)s/alembic/versions",
    }


def test_generate_alembic_ini_rejects_newline_in_version_table():
    with pytest.raises(ValueError):
        AlembicTemplates.generate_alembic_ini(
            **_base_kwargs(),
            version_table=INJECTION_PAYLOAD,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "script_location": INJECTION_PAYLOAD,
            "version_locations": "%(here)s/alembic/versions",
        },
        {
            "script_location": "alembic",
            "version_locations": INJECTION_PAYLOAD,
        },
        {**_base_kwargs(), "version_table": INJECTION_PAYLOAD},
        {**_base_kwargs(), "version_table_schema": INJECTION_PAYLOAD},
        {**_base_kwargs(), "autogenerate_exclude_tables": INJECTION_PAYLOAD},
        {**_base_kwargs(), "autogenerate_exclude_tables": [INJECTION_PAYLOAD]},
    ],
)
def test_generate_alembic_ini_rejects_newline_in_every_option(kwargs):
    with pytest.raises(ValueError):
        AlembicTemplates.generate_alembic_ini(**kwargs)


@pytest.mark.parametrize(
    "bad_value",
    ['quoted"name', "semi;colon", "bracket[name]", "1leading_digit", "has space"],
)
def test_version_table_rejects_non_identifier(bad_value):
    with pytest.raises(ValueError):
        AlembicTemplates.generate_alembic_ini(
            **_base_kwargs(),
            version_table=bad_value,
        )


def test_generated_ini_roundtrips_through_configparser():
    content = AlembicTemplates.generate_alembic_ini(
        script_location="alembic",
        version_locations="%(here)s/alembic/versions",
        version_table="alembic_version_app",
        version_table_schema="migration_app",
        autogenerate_exclude_tables=["alembic_version_other"],
    )

    parser = configparser.RawConfigParser()
    parser.read_string(content)

    assert set(parser.options("alembic")) == {
        "script_location",
        "version_locations",
        "version_table",
        "version_table_schema",
        "autogenerate_exclude_tables",
        "path_separator",
    }
