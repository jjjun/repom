from contextlib import nullcontext
from pathlib import Path
import runpy
from types import SimpleNamespace

from alembic import context
import pytest
import sqlalchemy

import repom.utility


class AlembicConfigStub:
    config_file_name = None
    config_ini_section = "alembic"

    def __init__(self, version_table, autogenerate_exclude_tables=None):
        self.options = {}
        if version_table is not None:
            self.options["version_table"] = version_table
        if autogenerate_exclude_tables is not None:
            self.options["autogenerate_exclude_tables"] = (
                autogenerate_exclude_tables
            )

    def get_main_option(self, name, default=None):
        return self.options.get(name, default)

    def set_main_option(self, name, value):
        self.options[name] = value

    def get_section(self, name, default=None):
        return default


@pytest.mark.parametrize("offline_mode", [True, False])
@pytest.mark.parametrize(
    ("configured_version_table", "expected_version_table"),
    [
        (None, "alembic_version"),
        ("alembic_version_fast_domain", "alembic_version_fast_domain"),
    ],
)
def test_env_configures_version_table(
    monkeypatch,
    offline_mode,
    configured_version_table,
    expected_version_table,
):
    configured_options = {}
    alembic_config = AlembicConfigStub(configured_version_table)
    connection = object()
    connectable = SimpleNamespace(connect=lambda: nullcontext(connection))

    monkeypatch.setattr(context, "config", alembic_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: offline_mode)
    monkeypatch.setattr(
        context,
        "configure",
        lambda **options: configured_options.update(options),
    )
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    monkeypatch.setattr(repom.utility, "load_models", lambda **kwargs: None)
    monkeypatch.setattr(
        sqlalchemy,
        "engine_from_config",
        lambda *args, **kwargs: connectable,
    )

    env_path = Path(__file__).parents[2] / "alembic" / "env.py"
    env_globals = runpy.run_path(env_path)

    assert configured_options["version_table"] == expected_version_table
    assert configured_options["include_object"] is env_globals["include_object"]
    if not offline_mode:
        assert configured_options["connection"] is connection


@pytest.mark.parametrize(
    (
        "configured_exclusions",
        "expected_exclusions",
        "table_name",
        "expected_included",
    ),
    [
        (None, frozenset(), "ordinary_table", True),
        ("", frozenset(), "ordinary_table", True),
        (
            " alembic_version_fast_domain, , alembic_version_audit ",
            frozenset(
                {
                    "alembic_version_fast_domain",
                    "alembic_version_audit",
                }
            ),
            "alembic_version_fast_domain",
            False,
        ),
    ],
)
def test_env_configures_autogenerate_table_exclusions(
    monkeypatch,
    configured_exclusions,
    expected_exclusions,
    table_name,
    expected_included,
):
    configured_options = {}
    alembic_config = AlembicConfigStub(
        None,
        autogenerate_exclude_tables=configured_exclusions,
    )
    connection = object()
    connectable = SimpleNamespace(connect=lambda: nullcontext(connection))

    monkeypatch.setattr(context, "config", alembic_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(
        context,
        "configure",
        lambda **options: configured_options.update(options),
    )
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    monkeypatch.setattr(repom.utility, "load_models", lambda **kwargs: None)
    monkeypatch.setattr(
        sqlalchemy,
        "engine_from_config",
        lambda *args, **kwargs: connectable,
    )

    env_path = Path(__file__).parents[2] / "alembic" / "env.py"
    env_globals = runpy.run_path(env_path)

    assert (
        env_globals["autogenerate_exclude_tables"]
        == expected_exclusions
    )
    parse_table_names = env_globals["_parse_table_names"]
    assert parse_table_names(configured_exclusions) == expected_exclusions

    include_object = configured_options["include_object"]
    assert (
        include_object(object(), table_name, "table", True, None)
        is expected_included
    )
    assert include_object(object(), table_name, "table", False, None) is True
    assert include_object(object(), table_name, "column", True, None) is True
