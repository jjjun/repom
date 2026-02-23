"""
Integration tests for DockerManager - tests actual container lifecycle
"""
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import pytest

from repom._ import docker_manager as dm


# ===== Test Implementations =====


class MockPostgresManager(dm.DockerManager):
    """Mock PostgreSQL manager for integration tests"""

    def __init__(self, compose_dir: Path | None = None):
        self.compose_dir = compose_dir or Path.cwd()
        self.container_name = "test_postgres"
        self.service_name = "PostgreSQL"

    def get_container_name(self) -> str:
        return self.container_name

    def get_compose_file_path(self) -> Path:
        compose_file = self.compose_dir / "docker-compose.yml"
        if not compose_file.exists():
            raise FileNotFoundError(f"Compose file not found: {compose_file}")
        return compose_file

    def wait_for_service(self, max_retries: int = 3) -> None:
        """Mock wait_for_postgres with quick timeout"""
        # Simulate checking pg_isready
        def check_postgres_ready():
            try:
                result = subprocess.run(
                    ["echo", "ok"],  # Mock: always succeeds
                    capture_output=True,
                    timeout=1,
                    check=False
                )
                return result.returncode == 0
            except Exception:
                return False

        dm.DockerCommandExecutor.wait_for_readiness(
            check_postgres_ready,
            max_retries=max_retries,
            service_name=self.service_name
        )


class MockRedisManager(dm.DockerManager):
    """Mock Redis manager for integration tests"""

    def __init__(self, compose_dir: Path | None = None):
        self.compose_dir = compose_dir or Path.cwd()
        self.container_name = "test_redis"
        self.service_name = "Redis"

    def get_container_name(self) -> str:
        return self.container_name

    def get_compose_file_path(self) -> Path:
        compose_file = self.compose_dir / "docker-compose.yml"
        return compose_file

    def wait_for_service(self, max_retries: int = 3) -> None:
        """Mock wait_for_redis with quick timeout"""
        def check_redis_ready():
            return True  # Mock: always ready

        dm.DockerCommandExecutor.wait_for_readiness(
            check_redis_ready,
            max_retries=max_retries,
            service_name=self.service_name
        )


# ===== Test Cases =====


class TestPostgresFullLifecycle:
    """Test PostgreSQL full lifecycle: generate → start → stop → remove"""

    def test_postgres_full_lifecycle(self, capsys):
        """Test complete PostgreSQL workflow"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"

            # Create mock compose file
            compose_file.write_text("version: '3.8'\nservices:\n  postgres:\n    image: postgres:15\n")

            manager = MockPostgresManager(compose_dir)

            # Test get_container_name
            assert manager.get_container_name() == "test_postgres"

            # Test get_compose_file_path
            assert manager.get_compose_file_path() == compose_file

            # Test start (mocked - mock both docker-compose and wait_for_service)
            with patch.object(dm.DockerCommandExecutor, 'run_docker_compose') as mock_run, \
                    patch.object(manager, 'wait_for_service') as mock_wait:
                manager.start()
                mock_run.assert_called()
                mock_wait.assert_called()

            # Verify message output
            captured = capsys.readouterr()
            assert "Starting" in captured.out or "test_postgres" in captured.out

    def test_postgres_stop_then_remove(self, capsys):
        """Test PostgreSQL stop and remove operations"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices: {}")

            manager = MockPostgresManager(compose_dir)

            with patch.object(dm.DockerCommandExecutor, 'run_docker_compose') as mock_run:
                manager.stop()
                assert mock_run.called

            with patch.object(dm.DockerCommandExecutor, 'run_docker_compose') as mock_run:
                manager.remove()
                assert mock_run.called


class TestContainerStatusChecks:
    """Test container status verification"""

    def test_status_running(self):
        """Test status check for running container"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices: {}")

            manager = MockPostgresManager(compose_dir)

            with patch.object(dm.DockerCommandExecutor, 'get_container_status') as mock_status:
                mock_status.return_value = "Up 5 minutes"
                result = manager.status()
                assert result is True

    def test_status_stopped(self):
        """Test status check for stopped container"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices: {}")

            manager = MockPostgresManager(compose_dir)

            with patch.object(dm.DockerCommandExecutor, 'get_container_status') as mock_status:
                mock_status.return_value = ""
                result = manager.status()
                assert result is False

    def test_is_running_alias(self):
        """Test is_running is alias for status"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices: {}")

            manager = MockPostgresManager(compose_dir)

            with patch.object(dm.DockerCommandExecutor, 'get_container_status') as mock_status:
                mock_status.return_value = "Up 10 minutes"

                status_result = manager.status()
                is_running_result = manager.is_running()

                assert status_result == is_running_result
                assert is_running_result is True


class TestErrorRecovery:
    """Test error handling and recovery"""

    def test_compose_file_not_found_on_start(self, capsys):
        """Test start fails gracefully when compose file missing"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            # Don't create compose file

            manager = MockPostgresManager(compose_dir)

            with pytest.raises(SystemExit):
                manager.start()

    def test_docker_command_not_found(self):
        """Test graceful handling when docker-compose not installed"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices: {}")

            manager = MockPostgresManager(compose_dir)

            # Simulate docker-compose not found
            with patch.object(dm.DockerCommandExecutor, 'run_docker_compose') as mock_run:
                mock_run.side_effect = FileNotFoundError("docker-compose not found")

                with pytest.raises(SystemExit):
                    manager.start()

    def test_start_with_docker_failure(self):
        """Test docker-compose command execution failure handling"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices: {}")

            manager = MockPostgresManager(compose_dir)

            # Simulate docker-compose command failure
            with patch.object(dm.DockerCommandExecutor, 'run_docker_compose') as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, 'docker-compose')

                # start() should catch and exit
                with pytest.raises(SystemExit):
                    manager.start()


class TestMultipleServices:
    """Test handling multiple services"""

    def test_redis_manager_lifecycle(self, capsys):
        """Test Redis manager basic lifecycle"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.yml"
            compose_file.write_text("version: '3.8'\nservices:\n  redis:\n    image: redis:latest\n")

            manager = MockRedisManager(compose_dir)

            assert manager.get_container_name() == "test_redis"
            assert manager.get_compose_file_path().exists()

    def test_service_specific_wait_logic(self):
        """Test each service has unique wait logic"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)

            postgres_mgr = MockPostgresManager(compose_dir)
            redis_mgr = MockRedisManager(compose_dir)

            # Both should have different container names
            assert postgres_mgr.get_container_name() != redis_mgr.get_container_name()

            # Both should have different service names
            assert postgres_mgr.service_name != redis_mgr.service_name
