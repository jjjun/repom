"""Behavior tests for the shared Alembic pre-migration hook."""

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent


def _write_hook_module(tmp_path: Path) -> None:
    (tmp_path / "alembic_test_hooks.py").write_text(
        """
import os
from pathlib import Path


def configure_database(config):
    database_path = Path(os.environ["ALEMBIC_HOOK_TEST_DB"]).as_posix()
    config.db_url = f"sqlite:///{database_path}"
    return config


def record_database(config):
    marker_path = Path(os.environ["ALEMBIC_HOOK_TEST_MARKER"])
    marker_path.write_text(config.db_url, encoding="utf-8")


def reject_database(config):
    raise RuntimeError("database rejected by test hook")


not_callable = "invalid"
""".lstrip(),
        encoding="utf-8",
    )


def _write_alembic_ini(tmp_path: Path, hook_path: str | None) -> Path:
    config_text = (PROJECT_ROOT / "alembic.ini").read_text(encoding="utf-8")
    if hook_path is not None:
        config_text = config_text.replace(
            "[alembic]\n",
            f"[alembic]\npre_migration_hook = {hook_path}\n",
            1,
        )

    config_path = tmp_path / "alembic.ini"
    config_path.write_text(config_text, encoding="utf-8")
    return config_path


def _alembic_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["EXEC_ENV"] = "test"
    env["DB_TYPE"] = "sqlite"
    env["CONFIG_HOOK"] = "alembic_test_hooks:configure_database"
    env["ALEMBIC_HOOK_TEST_DB"] = str(tmp_path / "hook-test.sqlite3")
    env["ALEMBIC_HOOK_TEST_MARKER"] = str(tmp_path / "hook-called.txt")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(tmp_path), env.get("PYTHONPATH")))
    )
    return env


def _run_alembic(
    config_path: Path,
    env: dict[str, str],
    *command: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(config_path),
            *command,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_missing_pre_migration_hook_is_a_no_op(tmp_path):
    _write_hook_module(tmp_path)
    config_path = _write_alembic_ini(tmp_path, None)
    env = _alembic_env(tmp_path)

    result = _run_alembic(config_path, env, "upgrade", "head")

    assert result.returncode == 0, result.stderr
    assert not Path(env["ALEMBIC_HOOK_TEST_MARKER"]).exists()


@pytest.mark.parametrize(
    "command",
    [
        ("upgrade", "head"),
        ("upgrade", "head", "--sql"),
    ],
    ids=["online", "offline"],
)
def test_pre_migration_hook_runs_before_online_and_offline_migrations(
    tmp_path,
    command,
):
    _write_hook_module(tmp_path)
    config_path = _write_alembic_ini(
        tmp_path,
        "alembic_test_hooks:record_database",
    )
    env = _alembic_env(tmp_path)

    result = _run_alembic(config_path, env, *command)

    assert result.returncode == 0, result.stderr
    marker_path = Path(env["ALEMBIC_HOOK_TEST_MARKER"])
    assert marker_path.read_text(encoding="utf-8").startswith("sqlite:///")


def test_raising_pre_migration_hook_aborts_before_version_table_write(tmp_path):
    _write_hook_module(tmp_path)
    config_path = _write_alembic_ini(
        tmp_path,
        "alembic_test_hooks:reject_database",
    )
    env = _alembic_env(tmp_path)
    database_path = Path(env["ALEMBIC_HOOK_TEST_DB"])

    result = _run_alembic(config_path, env, "upgrade", "head")

    assert result.returncode != 0
    assert "database rejected by test hook" in result.stderr
    assert not database_path.exists()


def test_raising_pre_migration_hook_does_not_write_to_existing_database(
    tmp_path,
):
    _write_hook_module(tmp_path)
    config_path = _write_alembic_ini(
        tmp_path,
        "alembic_test_hooks:reject_database",
    )
    env = _alembic_env(tmp_path)
    database_path = Path(env["ALEMBIC_HOOK_TEST_DB"])
    with closing(sqlite3.connect(database_path)):
        pass

    result = _run_alembic(config_path, env, "upgrade", "head")

    assert result.returncode != 0
    assert "database rejected by test hook" in result.stderr
    with closing(sqlite3.connect(database_path)) as connection:
        version_rows = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
    assert version_rows == (0,)


@pytest.mark.parametrize(
    ("hook_path", "expected_message"),
    [
        (
            "missing_alembic_hook_module:validate",
            "Failed to import config hook module",
        ),
        (
            "alembic_test_hooks:missing",
            "Config hook function",
        ),
        (
            "alembic_test_hooks:not_callable",
            "Config hook target",
        ),
        (
            "alembic_test_hooks",
            "must use 'module:function_name' format",
        ),
    ],
    ids=[
        "missing-module",
        "missing-function",
        "non-callable",
        "implicit-callable",
    ],
)
def test_invalid_pre_migration_hook_reports_its_alembic_option(
    tmp_path,
    hook_path,
    expected_message,
):
    _write_hook_module(tmp_path)
    config_path = _write_alembic_ini(tmp_path, hook_path)
    env = _alembic_env(tmp_path)

    result = _run_alembic(config_path, env, "upgrade", "head")

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert f"pre_migration_hook='{hook_path}'" in result.stderr
