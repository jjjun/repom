"""Tests for repom_info script."""

import os
from pathlib import Path
from unittest.mock import Mock, patch
from importlib.metadata import entry_points

from sqlalchemy.exc import OperationalError

from repom.scripts.repom_info import (
    display_config,
    format_size,
    get_db_file_info,
    get_loaded_models,
    main,
    parse_postgres_url,
    test_postgres_connection as check_postgres_connection,
    test_redis_connection as check_redis_connection,
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

    @patch('repom.diagnostics.database_info.config_module.config')
    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_sqlite(self, mock_script_config, mock_database_config, tmp_path):
        """Test SQLite file info retrieval."""
        # Create a test database file
        db_file = tmp_path / "test.db"
        db_file.write_text("test data")

        mock_script_config.db_type = 'sqlite'
        mock_database_config.db_type = 'sqlite'
        mock_database_config.db_url = f'sqlite:///{db_file}'
        mock_database_config.root_path = tmp_path

        info = get_db_file_info()

        assert info is not None
        assert info['file_path'] == str(db_file)
        assert info['exists'] is True
        assert 'MB' in info['size_mb']

    @patch('repom.diagnostics.database_info.config_module.config')
    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_not_exists(self, mock_script_config, mock_database_config, tmp_path):
        """Test SQLite file info when file doesn't exist."""
        db_file = tmp_path / "nonexistent.db"

        mock_script_config.db_type = 'sqlite'
        mock_database_config.db_type = 'sqlite'
        mock_database_config.db_url = f'sqlite:///{db_file}'
        mock_database_config.root_path = tmp_path

        info = get_db_file_info()

        assert info is not None
        assert info['exists'] is False
        assert info['size_mb'] == 'N/A'

    @patch('repom.diagnostics.database_info.config_module.config')
    @patch('repom.scripts.repom_info.config')
    def test_get_db_file_info_memory(self, mock_script_config, mock_database_config):
        """Test SQLite in-memory database."""
        mock_script_config.db_type = 'sqlite'
        mock_database_config.db_type = 'sqlite'
        mock_database_config.db_url = 'sqlite:///:memory:'

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
        assert 'user' not in info
        assert 'password' not in info

    def test_parse_postgres_url_no_password(self):
        """Test parsing PostgreSQL URL without password."""
        url = "postgresql://user@localhost:5432/dbname"

        info = parse_postgres_url(url)

        assert info is not None
        assert info['host'] == 'localhost'
        assert info['port'] == '5432'
        assert info['database'] == 'dbname'

    def test_parse_postgres_url_password_with_at_symbol_does_not_leak(self):
        """A percent-encoded '@' in the password must not leak or break parsing."""
        sentinel_password = "p%40ssw0rd"
        url = f"postgresql://user:{sentinel_password}@localhost:5432/dbname"

        info = parse_postgres_url(url)

        assert info is not None
        assert info['host'] == 'localhost'
        assert info['port'] == '5432'
        assert info['database'] == 'dbname'
        assert sentinel_password not in str(info)
        assert "p@ssw0rd" not in str(info)

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

        assert '[NG] Not configured' in result

    @patch('repom.diagnostics.database_info.create_engine')
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
        mock_config.db_url = 'postgresql://test_user:test_pass@localhost:5432/test_db'
        mock_config.engine_kwargs = {
            'pool_pre_ping': True,
            'connect_args': {'connect_timeout': 10, 'application_name': 'myapp'},
        }

        # Mock successful connection
        mock_engine = Mock()
        mock_conn = Mock()
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=False)
        mock_conn.execute = Mock()
        mock_engine.dispose = Mock()
        mock_create_engine.return_value = mock_engine

        result = check_postgres_connection()

        assert result == '[OK] Connected'
        mock_engine.dispose.assert_called_once()

        # config.engine_kwargs must flow through (application_name preserved),
        # with only the connect timeout pinned to a short probe value.
        _, kwargs = mock_create_engine.call_args
        assert kwargs['connect_args']['application_name'] == 'myapp'
        assert kwargs['connect_args']['connect_timeout'] == 3
        assert kwargs['pool_pre_ping'] is True

    @patch('repom.diagnostics.database_info.create_engine')
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
        mock_config.db_url = 'postgresql://test_user:test_pass@localhost:5432/test_db'
        mock_config.engine_kwargs = {'connect_args': {}}

        # Mock connection failure
        mock_create_engine.side_effect = OperationalError("Connection failed", None, None)

        result = check_postgres_connection()

        assert '[NG] Failed' in result

    @patch('repom.diagnostics.database_info.create_engine')
    @patch('repom.scripts.repom_info.config')
    def test_connection_test_disposes_engine_when_connect_raises(self, mock_config, mock_create_engine):
        """The engine must be disposed even when engine.connect() itself fails,
        not just when create_engine() fails - otherwise a failing check leaks
        the engine (repom#163).
        """
        mock_postgres = Mock()
        mock_postgres.host = 'localhost'
        mock_config.postgres = mock_postgres
        mock_config.postgres_db = 'test_db'
        mock_config.db_url = 'postgresql://test_user:test_pass@localhost:5432/test_db'
        mock_config.engine_kwargs = {'connect_args': {}}

        mock_engine = Mock()
        mock_engine.connect.side_effect = OperationalError("Connection failed", None, None)
        mock_create_engine.return_value = mock_engine

        result = check_postgres_connection()

        assert '[NG] Failed' in result
        mock_engine.dispose.assert_called_once()


class TestRedisConnectionTest:
    """Tests for test_redis_connection function."""

    @patch('redis.Redis')
    @patch('repom.scripts.repom_info.config')
    def test_redis_connection_passes_password_and_db(self, mock_config, mock_redis_cls):
        """The client must be constructed with the configured password and db,
        since repom's Redis containers always run with requirepass set
        (repom#163).
        """
        mock_config.redis.host = 'localhost'
        mock_config.redis.port = 6379
        mock_config.redis.password = 'secret'
        mock_config.redis.database = 2
        mock_redis_cls.return_value = Mock()

        result = check_redis_connection()

        assert result == '[OK] Connected'
        _, kwargs = mock_redis_cls.call_args
        assert kwargs['password'] == 'secret'
        assert kwargs['db'] == 2

    @patch('redis.Redis')
    @patch('repom.scripts.repom_info.config')
    def test_redis_connection_empty_password_becomes_none(self, mock_config, mock_redis_cls):
        """An empty-string password (the RepomConfig default) must be sent as
        None rather than as an empty-string credential.
        """
        mock_config.redis.host = 'localhost'
        mock_config.redis.port = 6379
        mock_config.redis.password = ''
        mock_config.redis.database = 0
        mock_redis_cls.return_value = Mock()

        check_redis_connection()

        _, kwargs = mock_redis_cls.call_args
        assert kwargs['password'] is None

    @patch('redis.Redis')
    @patch('repom.scripts.repom_info.config')
    def test_redis_connection_authentication_error(self, mock_config, mock_redis_cls):
        """An AuthenticationError (a ConnectionError subclass) must be reported
        as an authentication failure, not misreported as "Connection refused".
        """
        import redis

        mock_config.redis.host = 'localhost'
        mock_config.redis.port = 6379
        mock_config.redis.password = 'wrong'
        mock_config.redis.database = 0
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.AuthenticationError("NOAUTH Authentication required.")
        mock_redis_cls.return_value = mock_redis

        result = check_redis_connection()

        assert result == '[NG] Authentication failed'

    @patch('redis.Redis')
    @patch('repom.scripts.repom_info.config')
    def test_redis_connection_refused(self, mock_config, mock_redis_cls):
        """A plain connection failure is still reported as connection refused."""
        import redis

        mock_config.redis.host = 'localhost'
        mock_config.redis.port = 6379
        mock_config.redis.password = None
        mock_config.redis.database = 0
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.ConnectionError("Connection refused")
        mock_redis_cls.return_value = mock_redis

        result = check_redis_connection()

        assert result == '[NG] Connection refused'


class TestGetLoadedModels:
    """Tests for get_loaded_models function."""

    @patch('repom.scripts.repom_info.describe_loaded_models')
    def test_get_loaded_models_with_models(self, mock_describe):
        """Test retrieving loaded models."""
        from repom.utility import ModelInfo

        mock_describe.return_value = (
            [
                ModelInfo(
                    name='User',
                    qualified_name='repom.examples.models.user.User',
                    table_name='users',
                    primary_key=['id'],
                    column_count=3,
                )
            ],
            [],
        )

        models, failures = get_loaded_models()

        assert len(models) == 1
        assert models[0]['model_name'] == 'User'
        assert models[0]['table_name'] == 'users'
        assert models[0]['package'] == 'repom.examples.models.user.User'
        assert failures == []

    @patch('repom.scripts.repom_info.describe_loaded_models')
    def test_get_loaded_models_empty(self, mock_describe):
        """Test retrieving when no models loaded."""
        mock_describe.return_value = ([], [])

        models, failures = get_loaded_models()

        assert len(models) == 0
        assert failures == []

    @patch('repom.scripts.repom_info.describe_loaded_models')
    def test_get_loaded_models_returns_discovery_failures(self, mock_describe):
        """A partial load (some modules failed, others succeeded) is surfaced, not discarded."""
        from basekit.discovery import DiscoveryFailure

        mock_describe.return_value = (
            [],
            [
                DiscoveryFailure(
                    target='myapp.models.broken',
                    target_type='module',
                    exception_type='ImportError',
                    message='cannot import name broken_dependency',
                )
            ],
        )

        models, failures = get_loaded_models()

        assert len(failures) == 1
        assert failures[0].target == 'myapp.models.broken'
        assert failures[0].message == 'cannot import name broken_dependency'

    def test_get_loaded_models_schema_qualified_table_has_no_deprecation_warning(self):
        """A model whose table lives in a non-default schema must be reported
        under its real class name and "schema.table" full name. The old
        implementation matched Base.metadata.tables (keyed "schema.table")
        against the deprecated Mapper.mapped_table.name (just "table"), so it
        never matched and fell back to model_name=table_name,
        package='Unknown' while also emitting a SADeprecationWarning
        (repom#165).
        """
        import warnings

        from sqlalchemy import Integer
        from sqlalchemy.exc import SADeprecationWarning
        from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

        class ScratchBase(DeclarativeBase):
            pass

        class AuditThing(ScratchBase):
            __tablename__ = 'audit_things'
            __table_args__ = {'schema': 'aux'}

            id: Mapped[int] = mapped_column(Integer, primary_key=True)

        with patch('repom.models.base_model.Base', ScratchBase):
            with warnings.catch_warnings():
                warnings.simplefilter('error', SADeprecationWarning)
                models, failures = get_loaded_models()

        assert failures == []
        assert len(models) == 1
        assert models[0]['model_name'] == 'AuditThing'
        assert models[0]['table_name'] == 'aux.audit_things'

    def test_get_loaded_models_disallowed_location_reports_failure(self):
        """A model location outside allowed_package_prefixes raises a
        security ValueError from import_from_packages. It must be caught
        and reported as a DiscoveryFailure, not left to propagate, so the
        diagnostic command still prints its report (repom#165).
        """
        from repom.config import config

        original_locations = config.model_locations
        original_prefixes = config.allowed_package_prefixes
        original_strict = config.model_import_strict

        try:
            config.model_locations = ['os']
            config.allowed_package_prefixes = {'repom.'}
            config.model_import_strict = False

            models, failures = get_loaded_models()
        finally:
            config.model_locations = original_locations
            config.allowed_package_prefixes = original_prefixes
            config.model_import_strict = original_strict

        assert len(failures) == 1
        assert failures[0].target == 'os'
        assert failures[0].exception_type == 'ValueError'
        assert 'not in allowed list' in failures[0].message


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
        mock_get_models.return_value = (
            [
                {
                    'model_name': 'User',
                    'table_name': 'users',
                    'package': 'repom.examples.models.user.User'
                }
            ],
            [],
        )

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
        mock_check_conn.return_value = '[OK] Connected'
        mock_get_models.return_value = ([], [])

        display_config()

        captured = capsys.readouterr()
        assert 'postgresql' in captured.out
        assert 'PostgreSQL Details' in captured.out
        assert 'localhost' in captured.out
        assert '5432' in captured.out
        assert 'repom_test' in captured.out
        assert '[OK] Connected' in captured.out
        assert 'EXEC_ENV          : test' in captured.out
        assert 'CONFIG_HOOK       : test.config:get_config' in captured.out

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.test_postgres_connection')
    @patch('repom.scripts.repom_info.test_redis_connection')
    @patch('repom.scripts.repom_info.get_loaded_models')
    def test_repom_info_does_not_print_password(
        self, mock_get_models, mock_check_redis, mock_check_postgres, mock_config, capsys
    ):
        """A password embedded in the DB URL must never reach stdout, even
        when it contains a percent-encoded '@'. Uses the real
        parse_postgres_url() (not mocked) to exercise the actual leak path.
        """
        sentinel_password = "p%40ssw0rd"
        mock_config.root_path = Path('/test/path')
        mock_config.db_backup_path = Path('/test/path/data/repom/backups')
        mock_config.master_data_path = Path('/test/path/data_master')
        mock_config.db_type = 'postgres'
        mock_config.db_url = f'postgresql://user:{sentinel_password}@localhost:5432/repom_test'
        mock_config.model_locations = []
        mock_config.allowed_package_prefixes = set()
        mock_config.model_excluded_dirs = set()
        mock_config.pgadmin.container.enabled = False

        mock_check_postgres.return_value = '[OK] Connected'
        mock_check_redis.return_value = '[OK] Connected'
        mock_get_models.return_value = ([], [])

        display_config()

        captured = capsys.readouterr()
        assert sentinel_password not in captured.out
        assert "p@ssw0rd" not in captured.out
        assert 'localhost' in captured.out

    @patch('repom.scripts.repom_info.config')
    @patch('repom.scripts.repom_info.get_db_file_info')
    @patch('repom.scripts.repom_info.test_postgres_connection')
    @patch('repom.scripts.repom_info.get_loaded_models')
    def test_repom_info_reports_import_failures(
        self, mock_get_models, mock_check_conn, mock_get_db_info, mock_config, capsys
    ):
        """A model module that failed to import must be named in the output,
        not silently absent, so a partial load is diagnosable.
        """
        from basekit.discovery import DiscoveryFailure

        mock_config.root_path = Path('/test/path')
        mock_config.db_backup_path = Path('/test/path/data/repom/backups')
        mock_config.master_data_path = Path('/test/path/data_master')
        mock_config.db_type = 'sqlite'
        mock_config.db_url = 'sqlite:///data/repom/db.dev.sqlite3'
        mock_config.model_locations = ['myapp.models']
        mock_config.allowed_package_prefixes = {'myapp.'}
        mock_config.model_excluded_dirs = set()

        mock_get_db_info.return_value = {
            'file_path': '/test/path/data/repom/db.dev.sqlite3',
            'exists': True,
            'size_mb': '2.50 MB'
        }
        mock_check_conn.return_value = '(Not applicable for SQLite)'
        mock_get_models.return_value = (
            [],
            [
                DiscoveryFailure(
                    target='myapp.models.broken',
                    target_type='module',
                    exception_type='ImportError',
                    message='cannot import name broken_dependency',
                )
            ],
        )

        display_config()

        captured = capsys.readouterr()
        assert 'Model Import Failures' in captured.out
        assert 'myapp.models.broken' in captured.out
        assert 'ImportError' in captured.out
        assert 'cannot import name broken_dependency' in captured.out


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

    def test_repom_info_console_script_is_registered(self):
        """Test that the repom_info console script is installed."""
        scripts = entry_points(group='console_scripts')
        repom_info = [script for script in scripts if script.name == 'repom_info']

        assert repom_info
        assert repom_info[0].value == 'repom.scripts.repom_info:main'
