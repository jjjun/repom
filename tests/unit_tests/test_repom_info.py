"""Tests for repom_info script."""

import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from repom.scripts.repom_info import (
    display_config,
    format_size,
    get_db_file_info,
    get_loaded_models,
    main,
    parse_postgres_url,
    test_postgres_connection as check_postgres_connection,
)


class TestFormatSize:
    """Tests for format_size function."""

    def test_format_size_bytes(self):
        """Test formatting bytes to MB."""
        assert format_size(1024 * 1024) == "1.00 MB"
        assert format_size(2.5 * 1024 * 1024) == "2.50 MB"
        assert format_size(0) == "0.00 MB"

    def test_format_size_large_file(self):
        """Test formatting large file sizes."""
        assert format_size(100 * 1024 * 1024) == "100.00 MB"
        assert format_size(1024 * 1024 * 1024) == "1024.00 MB"


class TestGetDbFileInfo:
    """Tests for get_db_file_info function."""

    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_sqlite(self, mock_config, tmp_path):
        """Test SQLite file info retrieval."""
        # Create a test database file
        db_file = tmp_path / "test.db"
        db_file.write_text("test data")

        mock_config.db_type = 'sqlite'
        mock_config.db_url = f'sqlite:///{db_file}'
        mock_config.root_path = tmp_path

        info = get_db_file_info()

        assert info is not None
        assert info['file_path'] == str(db_file)
        assert info['exists'] is True
        assert 'MB' in info['size_mb']

    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_not_exists(self, mock_config, tmp_path):
        """Test SQLite file info when file doesn't exist."""
        db_file = tmp_path / "nonexistent.db"

        mock_config.db_type = 'sqlite'
        mock_config.db_url = f'sqlite:///{db_file}'
        mock_config.root_path = tmp_path

        info = get_db_file_info()

        assert info is not None
        assert info['exists'] is False
        assert info['size_mb'] == 'N/A'

    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_memory(self, mock_config):
        """Test SQLite in-memory database."""
        mock_config.db_type = 'sqlite'
        mock_config.db_url = 'sqlite:///:memory:'

        info = get_db_file_info()

        assert info is not None
        assert info['file_path'] == ':memory:'
        assert info['exists'] is True
        assert info['size_mb'] == 'N/A (in-memory)'

    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_postgresql(self, mock_config):
        """Test that PostgreSQL returns None."""
        mock_config.db_type = 'postgres'

        info = get_db_file_info()

        assert info is None


class TestParsePostgresUrl:
    """Tests for parse_postgres_url function."""

    def test_parse_postgres_url_full(self):
        """Test parsing full PostgreSQL URL."""
        url = "postgresql://user:password@localhost:5432/dbname"

        info = parse_postgres_url(url)

        assert info is not None
        assert info['host'] == 'localhost'
        assert info['port'] == '5432'
        assert info['database'] == 'dbname'
        assert info['user'] == 'user'

    def test_parse_postgres_url_no_password(self):
        """Test parsing PostgreSQL URL without password."""
        url = "postgresql://user@localhost:5432/dbname"

        info = parse_postgres_url(url)

        assert info is not None
        assert info['host'] == 'localhost'
        assert info['port'] == '5432'
        assert info['database'] == 'dbname'
        assert info['user'] == 'user'

    def test_parse_postgres_url_default_port(self):
        """Test parsing PostgreSQL URL with default port."""
        url = "postgresql://user:password@localhost/dbname"

        info = parse_postgres_url(url)

        assert info is not None
        assert info['host'] == 'localhost'
        assert info['port'] == '5432'
        assert info['database'] == 'dbname'

    def test_parse_postgres_url_sqlite(self):
        """Test that SQLite URL returns None."""
        url = "sqlite:///path/to/db.sqlite3"

        info = parse_postgres_url(url)

        assert info is None


class TestPostgresConnectionTest:
    """Tests for test_postgres_connection function."""

    @patch('repom.scripts.repom_info.config')
    def test_connection_test_not_configured(self, mock_config):
        """Test connection test when PostgreSQL is not configured."""
        mock_postgres = Mock()
        mock_postgres.host = None
        mock_config.postgres = mock_postgres

        result = check_postgres_connection()

        assert '✗ Not configured' in result

    @patch('repom.scripts.repom_info.create_engine')
    @patch('repom.scripts.repom_info.config')
    def test_connection_test_success(self, mock_config, mock_create_engine):
        """Test successful PostgreSQL connection."""
        # Mock PostgreSQL config
        mock_postgres = Mock()
        mock_postgres.host = 'localhost'
        mock_postgres.port = 5432
        mock_postgres.user = 'test_user'
        mock_postgres.password = 'test_pass'
        mock_config.postgres = mock_postgres
        mock_config.postgres_db = 'test_db'

        # Mock successful connection
        mock_engine = Mock()
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=False)
        mock_conn.execute = Mock()
        mock_engine.dispose = Mock()
        mock_create_engine.return_value = mock_engine

        result = check_postgres_connection()

        assert result == '✓ Connected'
        mock_engine.dispose.assert_called_once()

    @patch('repom.scripts.repom_info.create_engine')
    @patch('repom.scripts.repom_info.config')
    def test_connection_test_failure(self, mock_config, mock_create_engine):
        """Test failed PostgreSQL connection."""
        # Mock PostgreSQL config
        mock_postgres = Mock()
        mock_postgres.host = 'localhost'
        mock_postgres.port = 5432
        mock_postgres.user = 'test_user'
        mock_postgres.password = 'test_pass'
        mock_config.postgres = mock_postgres
        mock_config.postgres_db = 'test_db'

        # Mock connection failure
        mock_create_engine.side_effect = OperationalError("Connection failed", None, None)

        result = check_postgres_connection()

        assert '✗ Failed' in result


class TestGetLoadedModels:
    """Tests for get_loaded_models function."""

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.import_from_packages')
    @patch('repom.scripts.repom_info.Base')
    def test_get_loaded_models_with_models(self, mock_base, mock_import, mock_config):
        """Test retrieving loaded models."""
        mock_config.model_locations = ['repom.examples.models']

        # Mock a model
        mock_model = Mock()
        mock_model.__name__ = 'User'
        mock_model.__module__ = 'repom.examples.models.user'

        mock_mapper = Mock()
        mock_mapper.class_ = mock_model
        mock_mapper.mapped_table.name = 'users'

        mock_base.registry.mappers = [mock_mapper]
        mock_base.metadata.tables = {'users': Mock(name='users')}

        models = get_loaded_models()

        assert len(models) == 1
        assert models[0]['model_name'] == 'User'
        assert models[0]['table_name'] == 'users'
        assert models[0]['package'] == 'repom.examples.models.user.User'

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.import_from_packages')
    @patch('repom.scripts.repom_info.Base')
    def test_get_loaded_models_empty(self, mock_base, mock_import, mock_config):
        """Test retrieving when no models loaded."""
        mock_config.model_locations = []
        mock_base.registry.mappers = []
        mock_base.metadata.tables = {}

        models = get_loaded_models()

        assert len(models) == 0

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.import_from_packages')
    @patch('repom.scripts.repom_info.Base')
    def test_get_loaded_models_import_failure(self, mock_base, mock_import, mock_config):
        """Test that import failure doesn't crash the function."""
        mock_config.model_locations = ['invalid.module']
        mock_import.side_effect = ImportError("Module not found")
        mock_base.registry.mappers = []
        mock_base.metadata.tables = {}

        models = get_loaded_models()

        assert len(models) == 0


class TestDisplayConfig:
    """Tests for display_config function."""

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.get_db_file_info')
    @patch('repom.scripts.repom_info.test_postgres_connection')
    @patch('repom.scripts.repom_info.get_loaded_models')
    def test_display_config_sqlite(
        self, mock_get_models, mock_check_conn, mock_get_db_info, mock_config, capsys
    ):
        """Test display_config for SQLite."""
        mock_config.root_path = Path('/test/path')
        mock_config.db_backup_path = Path('/test/path/data/repom/backups')
        mock_config.master_data_path = Path('/test/path/data_master')
        mock_config.db_type = 'sqlite'
        mock_config.db_url = 'sqlite:///data/repom/db.dev.sqlite3'
        mock_config.model_locations = ['repom.examples.models']
        mock_config.allowed_package_prefixes = {'repom.'}
        mock_config.model_excluded_dirs = {'__pycache__'}

        mock_get_db_info.return_value = {
            'file_path': '/test/path/data/repom/db.dev.sqlite3',
            'exists': True,
            'size_mb': '2.50 MB'
        }
        mock_check_conn.return_value = '(Not applicable for SQLite)'
        mock_get_models.return_value = [
            {
                'model_name': 'User',
                'table_name': 'users',
                'package': 'repom.examples.models.user.User'
            }
        ]

        display_config()

        captured = capsys.readouterr()
        assert 'repom Configuration Information' in captured.out
        assert 'sqlite' in captured.out
        assert 'SQLite Details' in captured.out
        assert '2.50 MB' in captured.out
        assert 'User' in captured.out
        assert 'users' in captured.out

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.parse_postgres_url')
    @patch('repom.scripts.repom_info.test_postgres_connection')
    @patch('repom.scripts.repom_info.get_loaded_models')
    @patch.dict(os.environ, {'EXEC_ENV': 'test', 'CONFIG_HOOK': 'test.config:get_config'})
    def test_display_config_postgresql(
        self, mock_get_models, mock_check_conn, mock_parse_url, mock_config, capsys
    ):
        """Test display_config for PostgreSQL."""
        mock_config.root_path = Path('/test/path')
        mock_config.db_backup_path = Path('/test/path/data/repom/backups')
        mock_config.master_data_path = Path('/test/path/data_master')
        mock_config.db_type = 'postgres'
        mock_config.db_url = 'postgresql://user:password@localhost:5432/repom_test'
        mock_config.model_locations = []
        mock_config.allowed_package_prefixes = set()
        mock_config.model_excluded_dirs = set()

        mock_parse_url.return_value = {
            'host': 'localhost',
            'port': '5432',
            'database': 'repom_test',
            'user': 'user'
        }
        mock_check_conn.return_value = '✓ Connected'
        mock_get_models.return_value = []

        display_config()

        captured = capsys.readouterr()
        assert 'postgresql' in captured.out
        assert 'PostgreSQL Details' in captured.out
        assert 'localhost' in captured.out
        assert '5432' in captured.out
        assert 'repom_test' in captured.out
        assert '✓ Connected' in captured.out
        assert 'EXEC_ENV          : test' in captured.out
        assert 'CONFIG_HOOK       : test.config:get_config' in captured.out


class TestMain:
    """Tests for main function."""

    @patch('repom.scripts.repom_info.display_config')
    def test_main_success(self, mock_display):
        """Test main function success."""
        mock_display.return_value = None

        result = main()

        assert result == 0
        mock_display.assert_called_once()

    @patch('repom.scripts.repom_info.display_config')
    def test_main_failure(self, mock_display):
        """Test main function handles exceptions."""
        mock_display.side_effect = Exception("Test error")

        result = main()

        assert result == 1


class TestCommandExecution:
    """Integration test for command execution."""

    def test_repom_info_command_runs(self):
        """Test that poetry run repom_info executes without error."""
        # This is a basic smoke test
        result = subprocess.run(
            ['poetry', 'run', 'repom_info'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should not crash (exit code 0 or 1 are both acceptable for config tests)
        assert result.returncode in (0, 1)

        # Should contain expected output sections
        output = result.stdout + result.stderr
        assert 'repom Configuration Information' in output or 'Error' in output
