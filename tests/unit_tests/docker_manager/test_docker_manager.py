"""Tests for DockerManager base class"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repom._.docker_manager import DockerManager


class _TestDockerManagerImpl(DockerManager):
    """テスト用の具体的な DockerManager 実装"""

    def __init__(self, container_name: str, compose_file: Path):
        self.container_name = container_name
        self.compose_file = compose_file

    def get_container_name(self) -> str:
        return self.container_name

    def get_compose_file_path(self) -> Path:
        if not self.compose_file.exists():
            raise FileNotFoundError(f"Compose file not found: {self.compose_file}")
        return self.compose_file

    def wait_for_service(self, max_retries: int = 30) -> None:
        # テスト用: 即座に成功
        pass


class TestDockerManagerStart:
    """start() メソッドのテスト"""

    def test_start_success(self, tmp_path, capsys):
        """正常に起動"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        manager = _TestDockerManagerImpl("test_container", compose_file)

        with patch("repom._.docker_manager.DockerCommandExecutor.run_docker_compose"):
            with patch.object(manager, "wait_for_service"):
                manager.start()
                captured = capsys.readouterr()
                assert "🐳" in captured.out
                assert "Starting test_container container..." in captured.out
                assert "✅" in captured.out

    def test_start_compose_file_not_found(self, tmp_path):
        """Compose ファイルが見つからない"""
        compose_file = tmp_path / "docker-compose.yml"  # 作成しない

        manager = _TestDockerManagerImpl("test_container", compose_file)

        # get_compose_file_path() が FileNotFoundError を raise するため、
        # start() が sys.exit(1) を呼び出す
        with pytest.raises(SystemExit):
            manager.start()

    def test_start_docker_compose_failure(self, tmp_path):
        """docker-compose コマンド失敗"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        manager = _TestDockerManagerImpl("test_container", compose_file)

        with patch("repom._.docker_manager.DockerCommandExecutor.run_docker_compose") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker-compose")
            with pytest.raises(SystemExit):
                manager.start()

    def test_start_wait_timeout(self, tmp_path):
        """wait_for_service タイムアウト"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        manager = _TestDockerManagerImpl("test_container", compose_file)

        with patch("repom._.docker_manager.DockerCommandExecutor.run_docker_compose"):
            with patch.object(manager, "wait_for_service") as mock_wait:
                mock_wait.side_effect = TimeoutError("Service did not start")
                with pytest.raises(SystemExit):
                    manager.start()


class TestDockerManagerStop:
    """stop() メソッドのテスト"""

    def test_stop_success(self, tmp_path, capsys):
        """正常に停止"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        manager = _TestDockerManagerImpl("test_container", compose_file)

        with patch("repom._.docker_manager.DockerCommandExecutor.run_docker_compose"):
            manager.stop()
            captured = capsys.readouterr()
            assert "🛑" in captured.out
            assert "Stopping test_container container..." in captured.out
            assert "✅" in captured.out

    def test_stop_compose_file_not_found(self, tmp_path):
        """Compose ファイルが見つからない"""
        compose_file = tmp_path / "docker-compose.yml"  # 作成しない

        manager = _TestDockerManagerImpl("test_container", compose_file)

        # エラーを raise しないで、単に return する
        manager.stop()  # FileNotFoundError は raise されない


class TestDockerManagerRemove:
    """remove() メソッドのテスト"""

    def test_remove_success(self, tmp_path, capsys):
        """正常に削除"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3.8'\n")

        manager = _TestDockerManagerImpl("test_container", compose_file)

        with patch("repom._.docker_manager.DockerCommandExecutor.run_docker_compose"):
            manager.remove()
            captured = capsys.readouterr()
            assert "🧹" in captured.out
            assert "Removing test_container container and volumes..." in captured.out
            assert "✅" in captured.out

    def test_remove_compose_file_not_found(self, tmp_path):
        """Compose ファイルが見つからない"""
        compose_file = tmp_path / "docker-compose.yml"  # 作成しない

        manager = _TestDockerManagerImpl("test_container", compose_file)

        # エラーを raise しないで、単に return する
        manager.remove()  # FileNotFoundError は raise されない


class TestDockerManagerStatus:
    """status() メソッドのテスト"""

    def test_status_running(self):
        """コンテナ実行中"""
        manager = _TestDockerManagerImpl("test_container", Path("/tmp/compose.yml"))

        with patch("repom._.docker_manager.DockerCommandExecutor.get_container_status") as mock:
            mock.return_value = "Up 10 minutes"
            assert manager.status() is True

    def test_status_stopped(self):
        """コンテナ停止中"""
        manager = _TestDockerManagerImpl("test_container", Path("/tmp/compose.yml"))

        with patch("repom._.docker_manager.DockerCommandExecutor.get_container_status") as mock:
            mock.return_value = ""
            assert manager.status() is False

    def test_is_running_alias(self):
        """is_running() は status() の alias"""
        manager = _TestDockerManagerImpl("test_container", Path("/tmp/compose.yml"))

        with patch("repom._.docker_manager.DockerCommandExecutor.get_container_status") as mock:
            mock.return_value = "Up 5 minutes"
            assert manager.is_running() is True
