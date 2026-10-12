"""Unit tests: Alembic configuration for an external project.

This test verifies that an external project relies on its own alembic.ini
configuration (script_location/version_locations). RepomConfig does not
control migration version locations; alembic.ini is the sole source of truth.

Expected behavior:
- Version locations are controlled solely by alembic.ini
- repom's old migrations should NOT be referenced
"""
import pytest
import tempfile
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile
from alembic import command
from alembic.config import Config
from repom.alembic import AlembicSetup, SCRIPT_LOCATION, script_location_path
from repom.config import RepomConfig, config as repom_config


def test_alembic_versions_path_isolation():
    """Verify that version_locations are controlled by alembic.ini, not RepomConfig"""

    # Create temp directory for external project
    with tempfile.TemporaryDirectory() as tmpdir:
        external_versions_path = Path(tmpdir) / 'external_migrations' / 'versions'
        external_versions_path.mkdir(parents=True)

        # Create a minimal alembic.ini that points version_locations to the custom path
        alembic_ini = Path(tmpdir) / "alembic.ini"
        alembic_ini.write_text(
            "\n".join([
                "[alembic]",
                f"script_location = {SCRIPT_LOCATION}",
                f"version_locations = {external_versions_path}",
                "",
                "[loggers]",
                "keys = root",
                "",
                "[handlers]",
                "keys = console",
                "",
                "[formatters]",
                "keys = generic",
                "",
                "[logger_root]",
                "level = WARN",
                "handlers = console",
                "qualname =",
                "",
                "[handler_console]",
                "class = StreamHandler",
                "args = (sys.stderr,)",
                "level = NOTSET",
                "formatter = generic",
                "",
                "[formatter_generic]",
                "format = %(levelname)-5.5s [%(name)s] %(message)s",
            ]),
            encoding="utf-8",
        )

        # RepomConfig does not control version locations.
        config = RepomConfig()
        with pytest.raises(AttributeError):
            _ = config.alembic_versions_path  # noqa: B018

        alembic_config = Config(str(alembic_ini))
        assert alembic_config.get_main_option("version_locations") == str(external_versions_path)


def test_repom_has_no_migration_files():
    """Verify that the repository's alembic/versions/ has no migration files."""
    repom_root = Path(__file__).resolve().parents[2]
    repom_versions_dir = repom_root / 'alembic' / 'versions'

    # repom should not have migration files
    # Migration files should be in consuming applications (mine-py, etc.)
    if repom_versions_dir.exists():
        migration_files = [f for f in repom_versions_dir.glob('*.py') if f.name != '__init__.py']

        # Assert that repom has NO migration files
        assert len(migration_files) == 0, (
            f"[NG] repom should not have migration files, but found {len(migration_files)}:\n" +
            "\n".join(f"  - {f.name}" for f in migration_files) +
            "\n\nrepom is a library and should not contain its own migrations."
        )

        print("\n[OK] repository alembic/versions/ is empty (correct)")

        # .gitkeep should exist to preserve the directory
        gitkeep = repom_versions_dir / '.gitkeep'
        assert gitkeep.exists(), "alembic/versions/.gitkeep should exist"


def test_env_py_uses_version_locations_in_context():
    """Verify that env.py defers version_locations control to alembic.ini"""

    # Read env.py to check implementation
    env_py_path = script_location_path() / 'env.py'

    env_py_content = env_py_path.read_text()

    # env.py should no longer pass version_locations explicitly (alembic.ini is the source of truth)
    assert 'version_locations=' not in env_py_content, (
        "env.py should not hardcode version_locations; alembic.ini controls it."
    )


def test_mock_external_project_migration_paths_resolve_from_alembic_ini():
    repository_root = Path(__file__).resolve().parents[2]
    fixture_root = repository_root / "tests" / "integration_tests" / "mock_external_project"
    alembic_config = Config(str(fixture_root / "alembic.ini"))

    script_location = alembic_config.get_main_option("script_location")
    version_locations = Path(alembic_config.get_main_option("version_locations")).resolve()

    assert script_location == SCRIPT_LOCATION
    assert version_locations == fixture_root / "alembic" / "versions"


def test_default_script_location_runs_real_alembic_commands(tmp_path, monkeypatch):
    database_path = tmp_path / "migrations.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(repom_config, "root_path", str(tmp_path))
    monkeypatch.setattr(repom_config, "db_url", database_url)
    monkeypatch.setattr(repom_config, "model_locations", [])
    monkeypatch.setattr(repom_config, "allowed_package_prefixes", {"repom."})

    setup = AlembicSetup(project_root=tmp_path, db_url=database_url)
    assert setup.script_location == SCRIPT_LOCATION
    assert RepomConfig().alembic_script_location == SCRIPT_LOCATION

    setup.create_alembic_ini()
    setup.create_version_directory()
    alembic_config = setup.get_alembic_config()

    assert alembic_config.get_main_option("script_location") == SCRIPT_LOCATION
    assert (script_location_path() / "env.py").is_file()
    assert (script_location_path() / "script.py.mako").is_file()

    command.revision(alembic_config, message="package resource", autogenerate=False)
    revisions = [
        revision
        for revision in setup.versions_dir.glob("*.py")
        if revision.name != "__init__.py"
    ]
    assert len(revisions) == 1

    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")


def test_built_wheel_contains_alembic_environment(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is unavailable")

    repository_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repository_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"uv build failed:\n{result.stderr}\n{result.stdout}"

    wheel_path = next(tmp_path.glob("*.whl"))
    with ZipFile(wheel_path) as wheel:
        wheel_files = set(wheel.namelist())

    assert "repom/alembic/env.py" in wheel_files
    assert "repom/alembic/script.py.mako" in wheel_files


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
