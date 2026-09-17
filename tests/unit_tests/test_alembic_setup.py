"""Unit tests for AlembicSetup class

Tests for the AlembicSetup utility class that provides
a unified interface for Alembic initialization and reset operations.
"""

import os
import tempfile
from pathlib import Path

from repom.alembic import AlembicSetup, AlembicTemplates


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
            assert setup.version_table is None
            assert setup.version_table_schema is None
            assert setup.autogenerate_exclude_tables is None
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

    def test_versions_dirs_defaults_to_single_entry_list(self):
        """versions_dirs mirrors versions_dir when constructed directly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(tmpdir, 'sqlite:///test.db')

            assert setup.versions_dirs == [setup.versions_dir]


class TestFromIni:
    """Tests for AlembicSetup.from_ini (repom#160)"""

    def test_from_ini_reads_version_table_and_schema(self, tmp_path):
        ini_path = tmp_path / "alembic.ini"
        ini_path.write_text(AlembicTemplates.generate_alembic_ini(
            script_location="alembic",
            version_locations="%(here)s/migrations_ns2",
            version_table="alembic_version_ns2",
            version_table_schema="migration_ns2"
        ))

        setup = AlembicSetup.from_ini(ini_path, "sqlite:///test.db")

        assert setup.version_table == "alembic_version_ns2"
        assert setup.version_table_schema == "migration_ns2"
        assert setup.script_location == "alembic"
        assert setup.versions_dir == tmp_path / "migrations_ns2"
        assert setup.versions_dirs == [tmp_path / "migrations_ns2"]

    def test_from_ini_defaults_when_options_absent(self, tmp_path):
        """A bare [alembic] section falls back the same way
        alembic.script.ScriptDirectory.from_config does:
        "<script_location>/versions"."""
        ini_path = tmp_path / "alembic.ini"
        ini_path.write_text("[alembic]\n")

        setup = AlembicSetup.from_ini(ini_path, "sqlite:///test.db")

        assert setup.version_table == "alembic_version"
        assert setup.version_table_schema is None
        assert setup.script_location == "alembic"
        assert setup.versions_dir == tmp_path / "alembic" / "versions"
        assert setup.versions_dirs == [tmp_path / "alembic" / "versions"]

    def test_from_ini_defaults_to_script_location_versions_when_absent(
        self, tmp_path
    ):
        """repom#160 review: a non-default script_location with no
        version_locations must still resolve next to it, not to the
        hard-coded "alembic/versions"."""
        ini_path = tmp_path / "alembic.ini"
        ini_path.write_text(
            "[alembic]\n"
            "script_location = submod/repom/alembic\n"
        )

        setup = AlembicSetup.from_ini(ini_path, "sqlite:///test.db")

        expected = tmp_path / "submod" / "repom" / "alembic" / "versions"
        assert setup.versions_dir == expected
        assert setup.versions_dirs == [expected]

    def test_from_ini_resolves_relative_version_locations_against_ini_dir(
        self, tmp_path
    ):
        """A relative path with no %(here)s must not resolve against cwd"""
        ini_path = tmp_path / "alembic.ini"
        ini_path.write_text(
            "[alembic]\n"
            "script_location = alembic\n"
            "version_locations = alembic/versions\n"
            "path_separator = os\n"
        )

        setup = AlembicSetup.from_ini(ini_path, "sqlite:///test.db")

        assert setup.versions_dir == tmp_path / "alembic" / "versions"

    def test_from_ini_supports_multiple_version_locations(self, tmp_path):
        version_locations = os.pathsep.join([
            "%(here)s/migrations_a",
            "%(here)s/migrations_b",
        ])
        ini_path = tmp_path / "alembic.ini"
        ini_path.write_text(
            "[alembic]\n"
            "script_location = alembic\n"
            f"version_locations = {version_locations}\n"
            "path_separator = os\n"
        )

        setup = AlembicSetup.from_ini(ini_path, "sqlite:///test.db")

        assert setup.versions_dirs == [
            tmp_path / "migrations_a",
            tmp_path / "migrations_b",
        ]
        # versions_dir keeps pointing at the first location for callers that
        # only care about a single directory (e.g. alembic_init's summary).
        assert setup.versions_dir == tmp_path / "migrations_a"


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
            assert (
                '# autogenerate_exclude_tables = '
                'alembic_version_fast_domain'
            ) in content
            assert (
                '# Optional: isolate an independent migration namespace.'
            ) in content
            assert '# Defaults to alembic_version when omitted.' in content
            assert (
                '# version_table = alembic_version_fast_domain'
            ) in content
            assert '\nversion_table = ' not in content
            assert (
                '# version_table_schema = migration_fast_domain'
            ) in content
            assert '\nversion_table_schema = ' not in content
            assert '[logger_alembic]' in content  # Logging configuration

    def test_create_alembic_ini_with_version_table(self):
        """create_alembic_ini writes a configured version table"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                tmpdir,
                'sqlite:///test.db',
                version_table='alembic_version_fast_domain'
            )
            setup.create_alembic_ini()

            content = (Path(tmpdir) / 'alembic.ini').read_text()

            assert (
                'version_table = alembic_version_fast_domain'
            ) in content

    def test_create_alembic_ini_with_version_table_schema(self):
        """create_alembic_ini writes a configured version table schema"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                tmpdir,
                'sqlite:///test.db',
                version_table_schema='migration_fast_domain'
            )
            setup.create_alembic_ini()

            content = (Path(tmpdir) / 'alembic.ini').read_text()

            assert (
                'version_table_schema = migration_fast_domain'
            ) in content

    def test_create_alembic_ini_with_exclusion_string(self):
        """create_alembic_ini writes a raw exclusion string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                tmpdir,
                'sqlite:///test.db',
                autogenerate_exclude_tables='alembic_version_fast_domain'
            )
            setup.create_alembic_ini()

            content = (Path(tmpdir) / 'alembic.ini').read_text()

            assert (
                'autogenerate_exclude_tables = '
                'alembic_version_fast_domain'
            ) in content
            assert (
                '# autogenerate_exclude_tables = '
                'alembic_version_fast_domain'
            ) not in content

    def test_create_alembic_ini_with_exclusion_sequence(self):
        """create_alembic_ini joins an exclusion sequence"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                tmpdir,
                'sqlite:///test.db',
                autogenerate_exclude_tables=[
                    'alembic_version_fast_domain',
                    'alembic_version_mine_py'
                ]
            )
            setup.create_alembic_ini()

            content = (Path(tmpdir) / 'alembic.ini').read_text()

            assert (
                'autogenerate_exclude_tables = '
                'alembic_version_fast_domain, alembic_version_mine_py'
            ) in content

    def test_create_alembic_ini_with_empty_exclusion_string(self):
        """create_alembic_ini treats an empty exclusion string as omitted"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                tmpdir,
                'sqlite:///test.db',
                autogenerate_exclude_tables=''
            )
            setup.create_alembic_ini()

            content = (Path(tmpdir) / 'alembic.ini').read_text()

            assert (
                '# autogenerate_exclude_tables = '
                'alembic_version_fast_domain'
            ) in content
            assert '\nautogenerate_exclude_tables = ' not in content

    def test_create_alembic_ini_with_empty_exclusion_sequence(self):
        """create_alembic_ini treats an empty exclusion sequence as omitted"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = AlembicSetup(
                tmpdir,
                'sqlite:///test.db',
                autogenerate_exclude_tables=[]
            )
            setup.create_alembic_ini()

            content = (Path(tmpdir) / 'alembic.ini').read_text()

            assert (
                '# autogenerate_exclude_tables = '
                'alembic_version_fast_domain'
            ) in content
            assert '\nautogenerate_exclude_tables = ' not in content

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

    def test_create_version_directory_creates_all_versions_dirs(self, tmp_path):
        """create_version_directory covers every entry in versions_dirs"""
        setup = AlembicSetup(tmp_path, 'sqlite:///test.db')
        migrations_a = tmp_path / 'migrations_a'
        migrations_b = tmp_path / 'migrations_b'
        setup.versions_dirs = [migrations_a, migrations_b]

        setup.create_version_directory()

        assert (migrations_a / '__init__.py').exists()
        assert (migrations_b / '__init__.py').exists()


class TestResetMigrations:
    """Tests for reset_migrations method"""

    def test_reset_migrations_passes_version_table(self, monkeypatch, tmp_path):
        created_with = {}

        class ResetStub:
            def __init__(self, **kwargs):
                created_with.update(kwargs)

        monkeypatch.setattr(
            "repom.alembic.setup.AlembicReset",
            ResetStub
        )
        setup = AlembicSetup(
            tmp_path,
            "sqlite:///test.db",
            version_table="alembic_version_app2"
        )

        setup.reset_migrations(drop_table=False, delete_files=False)

        assert created_with["version_table"] == "alembic_version_app2"

    def test_reset_migrations_passes_version_table_schema(
        self,
        monkeypatch,
        tmp_path
    ):
        created_with = {}

        class ResetStub:
            def __init__(self, **kwargs):
                created_with.update(kwargs)

        monkeypatch.setattr(
            "repom.alembic.setup.AlembicReset",
            ResetStub
        )
        setup = AlembicSetup(
            tmp_path,
            "sqlite:///test.db",
            version_table_schema="migration_app2"
        )

        setup.reset_migrations(drop_table=False, delete_files=False)

        assert created_with["version_table_schema"] == "migration_app2"

    def test_reset_migrations_passes_default_version_table(
        self,
        monkeypatch,
        tmp_path
    ):
        created_with = {}

        class ResetStub:
            def __init__(self, **kwargs):
                created_with.update(kwargs)

        monkeypatch.setattr(
            "repom.alembic.setup.AlembicReset",
            ResetStub
        )
        setup = AlembicSetup(tmp_path, "sqlite:///test.db")

        setup.reset_migrations(drop_table=False, delete_files=False)

        assert created_with["version_table"] == "alembic_version"

    def test_reset_migrations_deletes_files_from_every_version_location(
        self, tmp_path
    ):
        """repom#160: multiple version_locations must each be cleaned"""
        migrations_a = tmp_path / "migrations_a"
        migrations_b = tmp_path / "migrations_b"
        for versions_dir in (migrations_a, migrations_b):
            versions_dir.mkdir()
            (versions_dir / "__init__.py").touch()
        (migrations_a / "0001_a.py").write_text("# a")
        (migrations_b / "0001_b.py").write_text("# b")

        setup = AlembicSetup(tmp_path, "sqlite:///test.db")
        setup.versions_dirs = [migrations_a, migrations_b]

        setup.reset_migrations(drop_table=False)

        assert not (migrations_a / "0001_a.py").exists()
        assert not (migrations_b / "0001_b.py").exists()
        assert (migrations_a / "__init__.py").exists()
        assert (migrations_b / "__init__.py").exists()


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
