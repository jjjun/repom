"""Integration test: Alembic with external project (simulates mine-py scenario)

This test simulates the scenario where:
1. repom has old migration files in repom/alembic/versions/
2. External project (mine-py) wants to use its own alembic/versions/
3. CONFIG_HOOK sets custom alembic_versions_path

Expected behavior:
- Only external project's versions/ should be used
- repom's old migrations should NOT be referenced
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from repom.config import MineDbConfig


def test_alembic_versions_path_isolation():
    """Verify that custom alembic_versions_path completely isolates migration history"""

    # Simulate external project config
    class ExternalProjectConfig(MineDbConfig):
        def __init__(self, custom_path: str):
            super().__init__()
            self._alembic_versions_path = custom_path

    # Create temp directory for external project
    with tempfile.TemporaryDirectory() as tmpdir:
        external_versions_path = str(Path(tmpdir) / 'external_migrations' / 'versions')

        config = ExternalProjectConfig(external_versions_path)

        # Verify path is set correctly
        assert config.alembic_versions_path == external_versions_path

        # Verify it's different from repom's default
        repom_config = MineDbConfig()
        repom_config.root_path = str(Path(__file__).parent.parent.parent.parent)
        repom_config.init()

        assert config.alembic_versions_path != repom_config.alembic_versions_path


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
    """Verify that env.py passes version_locations to context.configure()"""

    # Read env.py to check implementation
    repom_root = Path(__file__).parent.parent.parent.parent
    env_py_path = repom_root / 'alembic' / 'env.py'

    env_py_content = env_py_path.read_text()

    # Check that version_locations is passed to context.configure() in both modes
    assert 'version_locations=db_config.alembic_versions_path' in env_py_content, (
        "env.py must pass version_locations parameter to context.configure()\n"
        "This ensures Alembic uses the custom path instead of script_location/versions/"
    )

    # Count occurrences (should be in both offline and online mode)
    count = env_py_content.count('version_locations=db_config.alembic_versions_path')
    assert count == 2, f"version_locations should be set in both offline and online mode (found {count})"

    print("\n✅ env.py correctly passes version_locations to context.configure()")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
