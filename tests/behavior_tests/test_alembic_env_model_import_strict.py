"""Behavior tests for the strict model-import guards in alembic/env.py.

load_models() now returns the DiscoveryFailure list instead of discarding it
(repom#138). alembic/env.py passes strict=True unconditionally, so a model
module that fails to import must abort the migration run rather than letting
autogenerate compare the database against a partial Base.metadata - a
partial metadata makes autogenerate propose dropping tables that still exist.
A separate guard refuses to proceed when model_locations is configured but
discovery finds zero tables, the catastrophic variant of the same problem.
"""

import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).parent.parent.parent


def _write_hook_module(tmp_path: Path, model_locations: list) -> None:
    (tmp_path / "alembic_model_import_test_hooks.py").write_text(
        f"""
import os
from pathlib import Path


def configure_database(config):
    database_path = Path(os.environ["ALEMBIC_MODEL_IMPORT_TEST_DB"]).as_posix()
    config.db_url = f"sqlite:///{{database_path}}"
    config.model_locations = {model_locations!r}
    config.allowed_package_prefixes = {{"tests.fixtures."}}
    return config
""".lstrip(),
        encoding="utf-8",
    )


def _alembic_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["EXEC_ENV"] = "test"
    env["DB_TYPE"] = "sqlite"
    env["CONFIG_HOOK"] = "alembic_model_import_test_hooks:configure_database"
    env["ALEMBIC_MODEL_IMPORT_TEST_DB"] = str(tmp_path / "model-import-test.sqlite3")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(tmp_path), env.get("PYTHONPATH")))
    )
    return env


def _run_alembic(env: dict, *command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *command],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_alembic_env_raises_on_import_failure(tmp_path):
    """A model module that fails to import must abort alembic entirely."""
    _write_hook_module(tmp_path, ["tests.fixtures.broken_import"])
    env = _alembic_env(tmp_path)

    result = _run_alembic(env, "current")

    assert result.returncode != 0, result.stdout
    assert "tests.fixtures.broken_import.broken_model" in result.stderr
    assert "RuntimeError" in result.stderr


def test_autogenerate_refuses_when_no_models_discovered(tmp_path):
    """model_locations configured but discovering zero models must abort -
    the catastrophic case where autogenerate would propose dropping every
    table in the database.
    """
    _write_hook_module(tmp_path, ["tests.fixtures.empty_models"])
    env = _alembic_env(tmp_path)

    result = _run_alembic(env, "current")

    assert result.returncode != 0, result.stdout
    assert "no models were discovered" in result.stderr
