"""Tests for DockerCommandExecutor"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repom._.docker_manager import DockerCommandExecutor


class TestDockerComposeCommand:
    """docker-compose コマンド実行テスト"""

    def test_run_docker_compose_success(self, tmp_path):
        """docker-compose コマンド成功時"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            # エラーが発生しないことを確認
            DockerCommandExecutor.run_docker_compose("up -d", compose_file)
            mock_run.assert_called_once()

    def test_run_docker_compose_not_found(self, tmp_path):
        """docker-compose コマンド不在（FileNotFoundError）"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker-compose not found")
            with pytest.raises(FileNotFoundError) as exc_info:
                DockerCommandExecutor.run_docker_compose("up -d", compose_file)
            assert "docker-compose command not found" in str(exc_info.value)

    def test_run_docker_compose_failure(self, tmp_path):
        """docker-compose コマンド失敗（CalledProcessError）"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker-compose")
            with pytest.raises(subprocess.CalledProcessError):
                DockerCommandExecutor.run_docker_compose("up -d", compose_file)

    def test_run_docker_compose_capture_output(self, tmp_path):
        """出力をキャプチャする場合"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output")
            result = DockerCommandExecutor.run_docker_compose(
                "ps", compose_file, capture_output=True
            )
            assert result == "output"


class TestContainerStatus:
    """コンテナステータス取得テスト"""

    def test_get_container_status_running(self):
        """コンテナ実行中"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Up 10 minutes")
            status = DockerCommandExecutor.get_container_status("test_container")
            assert status == "Up 10 minutes"

    def test_get_container_status_stopped(self):
        """コンテナ停止中"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="Exited (0) 5 minutes ago")
            status = DockerCommandExecutor.get_container_status("test_container")
            assert "Exited" in status

    def test_get_container_status_not_found(self):
        """コンテナが見つからない"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            status = DockerCommandExecutor.get_container_status("nonexistent")
            assert status == ""

    def test_get_container_status_docker_not_found(self):
        """docker コマンド不在"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            with pytest.raises(FileNotFoundError) as exc_info:
                DockerCommandExecutor.get_container_status("test_container")
            assert "docker command not found" in str(exc_info.value)


class TestReadinessCheck:
    """Readiness check テスト"""

    def test_wait_for_readiness_success(self):
        """即座に成功"""
        check_func = MagicMock(return_value=True)
        # エラーが発生しないことを確認
        DockerCommandExecutor.wait_for_readiness(
            check_func, max_retries=5, interval_sec=0.01
        )
        check_func.assert_called_once()

    def test_wait_for_readiness_success_after_retries(self):
        """リトライ後に成功"""
        check_func = MagicMock(side_effect=[False, False, True])
        # エラーが発生しないことを確認
        DockerCommandExecutor.wait_for_readiness(
            check_func, max_retries=5, interval_sec=0.01
        )
        assert check_func.call_count == 3

    def test_wait_for_readiness_timeout(self):
        """タイムアウト"""
        check_func = MagicMock(return_value=False)
        with pytest.raises(TimeoutError) as exc_info:
            DockerCommandExecutor.wait_for_readiness(
                check_func, max_retries=3, interval_sec=0.01
            )
        assert "did not start within 3 seconds" in str(exc_info.value)
        assert check_func.call_count == 3

    def test_wait_for_readiness_custom_service_name(self):
        """カスタムサービス名でのtimeout メッセージ"""
        check_func = MagicMock(return_value=False)
        with pytest.raises(TimeoutError) as exc_info:
            DockerCommandExecutor.wait_for_readiness(
                check_func,
                max_retries=2,
                interval_sec=0.01,
                service_name="PostgreSQL",
            )
        assert "PostgreSQL" in str(exc_info.value)
