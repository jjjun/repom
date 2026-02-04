"""Unit tests for AlembicSetup class

Tests for the AlembicSetup utility class that provides
a unified interface for Alembic initialization and reset operations.
"""

import tempfile
import pytest
from pathlib import Path

from repom.alembic import AlembicSetup


class TestAlembicSetupInit:
    """Tests for AlembicSetup initialization"""

    def test_alembic_setup_initialization(self):
        """AlembicSetup can be initialized with minimal parameters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                project_root=tmpdir,
                db_url='sqlite:///test.db'
            )

            assert setup.project_root == Path(tmpdir)
            assert setup.db_url == 'sqlite:///test.db'
            assert setup.script_location == 'alembic'
            # version_locations preserves %(here)s placeholder
            assert setup.version_locations == '%(here)s/alembic/versions'
            # versions_dir has the expanded path
            expected_versions_dir = Path(tmpdir) / 'alembic' / 'versions'
            assert setup.versions_dir == expected_versions_dir

    def test_alembic_setup_with_custom_paths(self):
        """AlembicSetup accepts custom script_location and version_locations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                project_root=tmpdir,
                db_url='sqlite:///test.db',
                script_location='/custom/alembic',
                version_locations='/custom/versions'
            )

            assert setup.script_location == '/custom/alembic'
            assert setup.version_locations == '/custom/versions'

    def test_here_s_placeholder_expansion(self):
        """%(here)s placeholder is expanded in versions_dir"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                project_root=tmpdir,
                db_url='sqlite:///test.db',
                version_locations='%(here)s/migrations'
            )

            # version_locations preserves the placeholder
            assert setup.version_locations == '%(here)s/migrations'
            # versions_dir has the expanded path
            expected_dir = Path(tmpdir) / 'migrations'
            assert setup.versions_dir == expected_dir


class TestCreateAlembicIni:
    """Tests for create_alembic_ini method"""

    def test_create_alembic_ini_success(self):
        """create_alembic_ini creates alembic.ini file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')
            setup.create_alembic_ini()

            ini_path = Path(tmpdir) / 'alembic.ini'
            assert ini_path.exists()

    def test_create_version_directory_success(self):
        """create_version_directory creates directory with __init__.py"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')
            setup.create_version_directory()

            versions_dir = Path(tmpdir) / 'alembic' / 'versions'
            assert versions_dir.exists()
            assert versions_dir.is_dir()
            assert (versions_dir / '__init__.py').exists()

    def test_create_alembic_ini_content(self):
        """Generated alembic.ini contains correct configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')
            setup.create_alembic_ini()

            ini_path = Path(tmpdir) / 'alembic.ini'
            content = ini_path.read_text()

            assert '[alembic]' in content
            assert 'script_location' in content
            assert 'version_locations' in content
            assert '[logger_alembic]' in content  # Logging configuration

    def test_create_alembic_ini_does_not_overwrite_by_default(self):
        """create_alembic_ini does not overwrite existing file by default"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini_path = Path(tmpdir) / 'alembic.ini'
            ini_path.write_text('existing content')

            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')
            setup.create_alembic_ini(overwrite=False)

            # Original content should be preserved
            assert ini_path.read_text() == 'existing content'

    def test_create_alembic_ini_with_overwrite(self):
        """create_alembic_ini can overwrite existing file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini_path = Path(tmpdir) / 'alembic.ini'
            ini_path.write_text('old content')

            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')
            setup.create_alembic_ini(overwrite=True)

            # Content should be replaced
            new_content = ini_path.read_text()
            assert new_content != 'old content'
            assert '[alembic]' in new_content


class TestCreateVersionDirectory:
    """Tests for create_version_directory method"""

    def test_create_version_directory_idempotent(self):
        """create_version_directory is safe to call multiple times"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')

            # First call
            setup.create_version_directory()
            versions_dir = Path(tmpdir) / 'alembic' / 'versions'
            assert versions_dir.exists()

            # Second call should not fail
            setup.create_version_directory()
            assert versions_dir.exists()


class TestGetAlembicConfig:
    """Tests for get_alembic_config method"""

    def test_get_alembic_config_returns_config(self):
        """get_alembic_config returns AlembicConfig object"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')
            setup.create_alembic_ini()

            config = setup.get_alembic_config()

            from alembic.config import Config as AlembicConfig
            assert isinstance(config, AlembicConfig)

    def test_get_alembic_config_sets_db_url(self):
        """get_alembic_config sets sqlalchemy.url in config"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = 'sqlite:///custom.db'
            setup = AlembicSetup(tmpdir, db_url)
            setup.create_alembic_ini()

            config = setup.get_alembic_config()

            assert config.get_main_option('sqlalchemy.url') == db_url


class TestIntegration:
    """Integration tests for AlembicSetup"""

    def test_full_setup_workflow(self):
        """Complete workflow: init → create alembic.ini → create versions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')

            # Create alembic.ini
            setup.create_alembic_ini()
            assert (Path(tmpdir) / 'alembic.ini').exists()

            # Create version directory
            setup.create_version_directory()
            versions_dir = Path(tmpdir) / 'alembic' / 'versions'
            assert versions_dir.exists()
            assert (versions_dir / '__init__.py').exists()

            # Get AlembicConfig
            config = setup.get_alembic_config()
            assert config is not None

    def test_external_project_pattern(self):
        """Simulates external project setup (like mine-py)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # External project structure
            project_root = Path(tmpdir)
            repom_alembic = project_root / 'submod' / 'repom' / 'alembic'
            repom_alembic.mkdir(parents=True)

            # Setup for external project
            setup = AlembicSetup(
                project_root=str(project_root),
                db_url='sqlite:///data/mine_py/db.sqlite3',
                script_location=str(repom_alembic),
                version_locations=f'{tmpdir}/alembic/versions'
            )

            setup.create_alembic_ini()
            setup.create_version_directory()

            # Verify structure
            assert (project_root / 'alembic.ini').exists()
            assert (project_root / 'alembic' / 'versions').exists()

            # Verify alembic.ini content
            ini_content = (project_root / 'alembic.ini').read_text()
            assert 'submod/repom/alembic' in ini_content or 'submod\\repom\\alembic' in ini_content
