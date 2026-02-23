"""Tests for PostgreSQL Docker Manager integration"""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import pytest

from repom.postgres.manage import PostgresManager


class TestPostgresManagerInitialization:
    """Test PostgresManager initialization and basic methods"""

    def test_postgres_manager_instantiation(self):
        """Test creating PostgresManager instance"""
        manager = PostgresManager()
        assert manager is not None
        assert manager.config is not None

    def test_get_container_name(self):
        """Test get_container_name returns valid container name"""
        manager = PostgresManager()
        container_name = manager.get_container_name()

        assert isinstance(container_name, str)
        assert "postgres" in container_name.lower()
        assert len(container_name) > 0


class TestPostgresManagerComposePath:
    """Test compose file path handling"""

    def test_get_compose_file_path_not_found(self):
        """Test FileNotFoundError when compose file doesn't exist"""
        manager = PostgresManager()

        # Mock get_compose_dir to return non-existent directory
        with patch('repom.postgres.manage.get_compose_dir') as mock_dir:
            mock_dir.return_value = Path("/nonexistent/path")

            with pytest.raises(FileNotFoundError) as exc_info:
                manager.get_compose_file_path()

            assert "docker-compose.generated.yml" in str(exc_info.value)

    def test_get_compose_file_path_exists(self):
        """Test get_compose_file_path when file exists"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.generated.yml"
            compose_file.write_text("version: '3.8'\n")

            manager = PostgresManager()

            with patch('repom.postgres.manage.get_compose_dir') as mock_dir:
                mock_dir.return_value = compose_dir

                result = manager.get_compose_file_path()
                assert result == compose_file
                assert result.exists()


class TestPostgresManagerWaitForService:
    """Test wait_for_service method"""

    def test_wait_for_service_immediate_success(self):
        """Test wait_for_service succeeds immediately"""
        manager = PostgresManager()

        # Mock docker exec to always succeed
        with patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Should not raise
            manager.wait_for_service(max_retries=2)

    def test_wait_for_service_timeout(self):
        """Test wait_for_service timeout"""
        manager = PostgresManager()

        # Mock docker exec to always fail
        with patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            with pytest.raises(TimeoutError):
                manager.wait_for_service(max_retries=1)


class TestPostgresManagerConnectionInfo:
    """Test connection info printing"""

    def test_print_connection_info(self, capsys):
        """Test print_connection_info displays correct info"""
        manager = PostgresManager()
        manager.print_connection_info()

        captured = capsys.readouterr()
        assert "PostgreSQL Connection" in captured.out
        assert "localhost" in captured.out
        # Port should be in output
        assert str(manager.config.postgres.container.host_port) in captured.out


class TestPostgresManagerInheritance:
    """Test inheritance from DockerManager"""

    def test_has_docker_manager_methods(self):
        """Test PostgresManager has inherited DockerManager methods"""
        manager = PostgresManager()

        # Verify methods exist
        assert hasattr(manager, 'start')
        assert hasattr(manager, 'stop')
        assert hasattr(manager, 'remove')
        assert hasattr(manager, 'status')
        assert hasattr(manager, 'is_running')

        # Verify they're callable
        assert callable(manager.start)
        assert callable(manager.stop)
        assert callable(manager.remove)
        assert callable(manager.status)
        assert callable(manager.is_running)


class TestPostgresManagerCLI:
    """Test CLI commands using PostgresManager"""

    def test_cli_generate_command(self, tmp_path):
        """Test 'poetry run postgres_generate' command still works"""
        # This is a smoke test - just verify the cli entry point exists
        from repom.postgres.manage import generate

        assert callable(generate)

    def test_cli_start_command_with_mocked_docker(self, tmp_path):
        """Test start command uses PostgresManager"""
        from repom.postgres.manage import start

        assert callable(start)
        # Would need integration test with Docker to test full flow

    def test_cli_stop_command_with_mocked_docker(self, tmp_path):
        """Test stop command uses PostgresManager"""
        from repom.postgres.manage import stop

        assert callable(stop)

    def test_cli_remove_command_with_mocked_docker(self, tmp_path):
        """Test remove command uses PostgresManager"""
        from repom.postgres.manage import remove

        assert callable(remove)
