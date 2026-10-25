"""Unit tests for AlembicTemplates.generate_alembic_ini input validation.

A newline in an interpolated value ends the current ini key and starts a
new one; the shared repom/alembic/env.py trusts keys it reads from this file,
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


@pytest.mark.parametrize("option", ["script_location", "version_locations"])
def test_generate_alembic_ini_rejects_non_ascii_path_options(option):
    """The ini is written as UTF-8 but Alembic reads it with the locale
    encoding, so a non-ASCII path would fail on hosts such as cp932."""
    kwargs = {**_base_kwargs(), option: "migrations_テスト"}

    with pytest.raises(ValueError, match="ASCII only"):
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


def test_string_exclude_tables_are_written_from_validated_entries():
    content = AlembicTemplates.generate_alembic_ini(
        **_base_kwargs(),
        autogenerate_exclude_tables=(
            "alembic_version_other,\r\nalembic_version_second"
        ),
    )

    assert "autogenerate_exclude_tables = alembic_version_other, alembic_version_second" in content
    assert "\r" not in content
