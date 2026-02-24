"""Tests for Redis Docker Manager integration"""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import pytest

from repom.redis.manage import RedisManager


class TestRedisManagerInitialization:
    """Test RedisManager initialization and basic methods"""

    def test_redis_manager_instantiation(self):
        """Test creating RedisManager instance"""
        manager = RedisManager()
        assert manager is not None
        assert manager.config is not None

    def test_get_container_name(self):
        """Test get_container_name returns valid container name"""
        manager = RedisManager()
        container_name = manager.get_container_name()

        assert isinstance(container_name, str)
        assert container_name == "repom_redis"
        assert len(container_name) > 0


class TestRedisManagerComposePath:
    """Test compose file path handling"""

    def test_get_compose_file_path_not_found(self):
        """Test FileNotFoundError when compose file doesn't exist"""
        manager = RedisManager()

        # Mock get_compose_dir to return non-existent directory
        with patch('repom.redis.manage.get_compose_dir') as mock_dir:
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

            manager = RedisManager()

            with patch('repom.redis.manage.get_compose_dir') as mock_dir:
                mock_dir.return_value = compose_dir

                result = manager.get_compose_file_path()
                assert result == compose_file
                assert result.exists()


class TestRedisManagerWaitForService:
    """Test wait_for_service method"""

    def test_wait_for_service_immediate_success(self):
        """Test wait_for_service succeeds immediately with PONG response"""
        manager = RedisManager()

        # Mock docker exec to return PONG
        with patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="PONG\n"
            )

            # Should not raise
            manager.wait_for_service(max_retries=2)

    def test_wait_for_service_timeout(self):
        """Test wait_for_service timeout"""
        manager = RedisManager()

        # Mock docker exec to always fail
        with patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout=""
            )

            with pytest.raises(TimeoutError):
                manager.wait_for_service(max_retries=1)

    def test_wait_for_service_retries(self):
        """Test wait_for_service retries before success"""
        manager = RedisManager()

        # First 2 calls fail, 3rd succeeds
        side_effects = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=0, stdout="PONG\n"),
        ]

        with patch.object(subprocess, 'run') as mock_run:
            mock_run.side_effect = side_effects

            # Should not raise (succeeds after retries)
            manager.wait_for_service(max_retries=3)
            assert mock_run.call_count == 3


class TestRedisManagerConnectionInfo:
    """Test connection info printing"""

    def test_print_connection_info(self, capsys):
        """Test print_connection_info displays correct info"""
        manager = RedisManager()
        manager.print_connection_info()

        captured = capsys.readouterr()
        assert "Redis Connection" in captured.out
        assert "localhost" in captured.out
        assert str(manager.config.redis.port) in captured.out

    def test_print_connection_info_contains_cli_command(self, capsys):
        """Test print_connection_info shows CLI command"""
        manager = RedisManager()
        manager.print_connection_info()

        captured = capsys.readouterr()
        assert "redis-cli" in captured.out


class TestRedisManagerGenerate:
    """Test docker-compose and redis.conf generation"""

    def test_generate_redis_conf_content(self):
        """Test generate_redis_conf() returns valid config"""
        from repom.redis.manage import generate_redis_conf

        config = generate_redis_conf()

        assert isinstance(config, str)
        assert "appendonly yes" in config
        assert "databases 16" in config
        assert "maxmemory 256mb" in config
        assert "save 900 1" in config

    def test_generate_redis_conf_contains_comments(self):
        """Test generate_redis_conf includes configuration comments"""
        from repom.redis.manage import generate_redis_conf

        config = generate_redis_conf()

        assert "Database" in config
        assert "Persistence" in config
        assert "Snapshots" in config
        assert "Memory" in config


class TestRedisManagerInheritance:
    """Test DockerManager inheritance"""

    def test_redis_manager_inherits_from_docker_manager(self):
        """Test RedisManager properly inherits from DockerManager"""
        from repom._.docker_manager import DockerManager

        manager = RedisManager()
        assert isinstance(manager, DockerManager)

    def test_redis_manager_has_required_methods(self):
        """Test RedisManager has all required abstract methods implemented"""
        manager = RedisManager()

        # Check all required methods exist
        assert hasattr(manager, 'get_container_name')
        assert hasattr(manager, 'get_compose_file_path')
        assert hasattr(manager, 'wait_for_service')

        # Check all inherited methods exist
        assert hasattr(manager, 'start')
        assert hasattr(manager, 'stop')
        assert hasattr(manager, 'remove')
        assert hasattr(manager, 'status')
        assert hasattr(manager, 'is_running')

    def test_redis_manager_has_get_project_name(self):
        """Test RedisManager has get_project_name method"""
        manager = RedisManager()
        assert hasattr(manager, 'get_project_name')
        assert callable(manager.get_project_name)

    def test_redis_manager_get_project_name_returns_container_name(self):
        """Test get_project_name returns get_container_name value"""
        manager = RedisManager()
        project_name = manager.get_project_name()
        container_name = manager.get_container_name()

        # get_project_name should return the same value as get_container_name
        assert project_name == container_name
        assert isinstance(project_name, str)
        assert len(project_name) > 0


class TestRedisManagerCLI:
    """Test CLI command functions"""

    def test_generate_function_exists(self):
        """Test generate() function is callable"""
        from repom.redis.manage import generate

        assert callable(generate)

    def test_start_function_exists(self):
        """Test start() function is callable"""
        from repom.redis.manage import start

        assert callable(start)

    def test_stop_function_exists(self):
        """Test stop() function is callable"""
        from repom.redis.manage import stop

        assert callable(stop)

    def test_remove_function_exists(self):
        """Test remove() function is callable"""
        from repom.redis.manage import remove

        assert callable(remove)


class TestRedisManagerInitDir:
    """Test init directory handling"""

    def test_get_init_dir_creates_directory(self):
        """Test get_init_dir creates redis_init directory"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)

            with patch('repom.redis.manage.get_compose_dir') as mock_compose_dir:
                mock_compose_dir.return_value = compose_dir

                from repom.redis.manage import get_init_dir

                init_dir = get_init_dir()

                assert init_dir.exists()
                assert init_dir.name == "redis_init"
                assert init_dir.parent == compose_dir


class TestRedisDockerCompose:
    """Test docker-compose generation"""

    def test_generate_docker_compose_structure(self):
        """Test generate_docker_compose() returns valid structure"""
        from repom.redis.manage import generate_docker_compose

        generator = generate_docker_compose()

        # Check generator has correct type
        from repom._.docker_compose import DockerComposeGenerator
        assert isinstance(generator, DockerComposeGenerator)

    def test_docker_compose_yaml_content(self):
        """Test docker-compose YAML is properly formatted"""
        from repom.redis.manage import generate_docker_compose, RedisManager

        generator = generate_docker_compose()
        yaml_content = generator.generate()

        # Get config through RedisManager to use actual configured values
        manager = RedisManager()
        config = manager.config

        assert isinstance(yaml_content, str)
        assert "version:" in yaml_content
        assert "services:" in yaml_content
        assert "redis:" in yaml_content
        assert "repom_redis" in yaml_content
        # Check port mapping with actual config value (host_port:container_port)
        assert f"{config.redis.port}:6379" in yaml_content
        assert "healthcheck:" in yaml_content
        assert "redis-cli" in yaml_content


class TestRedisManagerErrorHandling:
    """Test error handling"""

    def test_wait_for_service_handles_exception(self):
        """Test wait_for_service handles subprocess exceptions"""
        manager = RedisManager()

        with patch.object(subprocess, 'run') as mock_run:
            mock_run.side_effect = Exception("Docker not available")

            with pytest.raises(TimeoutError):
                manager.wait_for_service(max_retries=1)

    def test_docker_exec_missing_container(self):
        """Test handling when container doesn't exist"""
        manager = RedisManager()

        with patch.object(subprocess, 'run') as mock_run:
            # Simulate 'docker: Error response from daemon'
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="docker: Error response from daemon"
            )

            with pytest.raises(TimeoutError):
                manager.wait_for_service(max_retries=1)
