"""Integration test: Alembic with external project (simulates mine-py scenario)

This test simulates the scenario where an external project relies on its own
alembic.ini configuration (script_location/version_locations) and no longer
expects repom to expose alembic_versions_path via RepomConfig.

Expected behavior:
- Version locations are controlled solely by alembic.ini
- repom's old migrations should NOT be referenced
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from alembic.config import Config
from repom.config import RepomConfig


def test_alembic_versions_path_isolation():
    """Verify that version_locations are controlled by alembic.ini, not RepomConfig"""

    # Simulate external project config
    class ExternalProjectConfig(RepomConfig):
        def __init__(self, custom_path: str):
            super().__init__()
            self._alembic_versions_path = custom_path

    # Create temp directory for external project
    with tempfile.TemporaryDirectory() as tmpdir:
        external_versions_path = Path(tmpdir) / 'external_migrations' / 'versions'
        external_versions_path.mkdir(parents=True)

        # Create a minimal alembic.ini that points version_locations to the custom path
        alembic_ini = Path(tmpdir) / "alembic.ini"
        alembic_ini.write_text(
            "\n".join([
                "[alembic]",
                f"script_location = {Path(__file__).parent.parent.parent.parent / 'alembic'}",
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

        # RepomConfig should not expose alembic_versions_path anymore
        config = ExternalProjectConfig(str(external_versions_path))
        with pytest.raises(AttributeError):
            _ = config.alembic_versions_path  # noqa: B018

        alembic_config = Config(str(alembic_ini))
        assert alembic_config.get_main_option("version_locations") == str(external_versions_path)


def test_repom_has_no_migration_files():
    """Verify that repom/alembic/versions/ is empty (library should not have migrations)"""
    repom_root = Path(__file__).parent.parent.parent.parent
    repom_versions_dir = repom_root / 'alembic' / 'versions'

    # repom should not have migration files
    # Migration files should be in consuming applications (mine-py, etc.)
    if repom_versions_dir.exists():
        migration_files = [f for f in repom_versions_dir.glob('*.py') if f.name != '__init__.py']

        # Assert that repom has NO migration files
        assert len(migration_files) == 0, (
            f"❌ repom should not have migration files, but found {len(migration_files)}:\n" +
            "\n".join(f"  - {f.name}" for f in migration_files) +
            "\n\nrepom is a library and should not contain its own migrations."
        )

        print(f"\n✅ repom/alembic/versions/ is empty (correct)")

        # .gitkeep should exist to preserve the directory
        gitkeep = repom_versions_dir / '.gitkeep'
        assert gitkeep.exists(), "alembic/versions/.gitkeep should exist"


def test_env_py_uses_version_locations_in_context():
    """Verify that env.py defers version_locations control to alembic.ini"""

    # Read env.py to check implementation
    repom_root = Path(__file__).parent.parent.parent.parent
    env_py_path = repom_root / 'alembic' / 'env.py'

    env_py_content = env_py_path.read_text()

    # env.py should no longer pass version_locations explicitly (alembic.ini is the source of truth)
    assert 'version_locations=' not in env_py_content, (
        "env.py should not hardcode version_locations; alembic.ini controls it."
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
