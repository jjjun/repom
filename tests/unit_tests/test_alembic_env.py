from contextlib import nullcontext
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace

from alembic import context
from alembic.config import Config
import pytest
import sqlalchemy

import repom.config
import repom.utility


class AlembicConfigStub:
    config_file_name = None
    config_ini_section = "alembic"

    def __init__(
        self,
        version_table,
        autogenerate_exclude_tables=None,
        version_table_schema=None,
    ):
        self.options = {}
        if version_table is not None:
            self.options["version_table"] = version_table
        if version_table_schema is not None:
            self.options["version_table_schema"] = version_table_schema
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


@pytest.mark.parametrize("offline_mode", [True, False])
@pytest.mark.parametrize(
    (
        "configured_version_table_schema",
        "expected_version_table_schema",
    ),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("migration_fast_domain", "migration_fast_domain"),
    ],
)
def test_env_configures_version_table_schema(
    monkeypatch,
    offline_mode,
    configured_version_table_schema,
    expected_version_table_schema,
):
    configured_options = {}
    alembic_config = AlembicConfigStub(
        None,
        version_table_schema=configured_version_table_schema,
    )
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
    runpy.run_path(env_path)

    assert (
        configured_options["version_table_schema"]
        == expected_version_table_schema
    )
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


def test_env_escapes_percent_signs_in_db_url_for_configparser(monkeypatch):
    """A '%' in the DSN (e.g. a percent-encoded password) must be escaped
    before reaching ConfigParser.

    Config.set_main_option() feeds the value straight into ConfigParser,
    which treats '%' as the start of an interpolation sequence. An
    unescaped '%' therefore makes ConfigParser raise
    ``ValueError: invalid interpolation syntax in '<the raw DSN>' ...``,
    embedding the full DSN - including the password - in the exception
    message. Doubling the '%' before calling set_main_option avoids that
    while still round-tripping to the original URL via get_main_option().
    """
    sentinel_password = "p%40ss"
    raw_url = f"postgresql://user:{sentinel_password}@localhost:5432/app"
    real_config = Config()
    connection = object()
    connectable = SimpleNamespace(connect=lambda: nullcontext(connection))

    monkeypatch.setattr(context, "config", real_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(context, "configure", lambda **options: None)
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    monkeypatch.setattr(repom.utility, "load_models", lambda **kwargs: None)
    monkeypatch.setattr(
        sqlalchemy,
        "engine_from_config",
        lambda *args, **kwargs: connectable,
    )
    monkeypatch.setattr(repom.config.config, "db_url", raw_url)

    env_path = Path(__file__).parents[2] / "alembic" / "env.py"
    # Must not raise: an unescaped '%' would make ConfigParser embed the
    # raw DSN (password included) in a ValueError here.
    runpy.run_path(env_path)

    assert real_config.get_main_option("sqlalchemy.url") == raw_url


def _run_env_with_pre_migration_hook(monkeypatch, hook_path):
    alembic_config = AlembicConfigStub(None)
    alembic_config.options["pre_migration_hook"] = hook_path
    connection = object()
    connectable = SimpleNamespace(connect=lambda: nullcontext(connection))

    monkeypatch.setattr(context, "config", alembic_config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(context, "configure", lambda **options: None)
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    monkeypatch.setattr(repom.utility, "load_models", lambda **kwargs: None)
    monkeypatch.setattr(
        sqlalchemy,
        "engine_from_config",
        lambda *args, **kwargs: connectable,
    )

    env_path = Path(__file__).parents[2] / "alembic" / "env.py"
    return runpy.run_path(env_path)


def test_pre_migration_hook_rejects_module_outside_allowed_prefixes(monkeypatch):
    """A newline injected into a generated alembic.ini could add a
    pre_migration_hook key naming an arbitrary module. Restricting the
    hook to allowed_package_prefixes means even a successfully injected
    key still cannot import an attacker-chosen module.
    """
    monkeypatch.setattr(
        repom.config.config, "allowed_package_prefixes", {"repom."}
    )

    with pytest.raises(ValueError):
        _run_env_with_pre_migration_hook(monkeypatch, "evil_module:run")


def test_pre_migration_hook_runs_when_module_is_within_allowed_prefixes(
    monkeypatch,
):
    monkeypatch.setattr(
        repom.config.config, "allowed_package_prefixes", {"repom."}
    )
    calls = []
    fake_module = ModuleType("repom.fake_pre_migration_hook")
    fake_module.run = lambda cfg: calls.append(cfg)
    monkeypatch.setitem(
        sys.modules, "repom.fake_pre_migration_hook", fake_module
    )

    _run_env_with_pre_migration_hook(
        monkeypatch, "repom.fake_pre_migration_hook:run"
    )

    assert calls == [repom.config.config]
