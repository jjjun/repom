"""Tests for the shared repom.docker_service helpers."""

import subprocess
from unittest.mock import MagicMock

import pytest
from basekit.docker_manager import DockerCommandExecutor

from repom.docker_service import DockerUnavailableError, is_container_running, start_service


def test_is_container_running_returns_underlying_result(monkeypatch):
    monkeypatch.setattr(
        DockerCommandExecutor, "is_container_running", MagicMock(return_value=True)
    )

    assert is_container_running("repom_postgres") is True


def test_is_container_running_raises_docker_unavailable_when_docker_missing(monkeypatch):
    monkeypatch.setattr(
        DockerCommandExecutor,
        "is_container_running",
        MagicMock(side_effect=FileNotFoundError("docker not found")),
    )

    with pytest.raises(DockerUnavailableError, match="docker command not found"):
        is_container_running("repom_postgres")


def test_is_container_running_raises_docker_unavailable_with_daemon_stderr(monkeypatch):
    original = subprocess.CalledProcessError(
        1, ["docker", "ps"], stderr="Cannot connect to the Docker daemon"
    )
    monkeypatch.setattr(
        DockerCommandExecutor,
        "is_container_running",
        MagicMock(side_effect=original),
    )

    with pytest.raises(
        DockerUnavailableError, match="Cannot connect to the Docker daemon"
    ) as excinfo:
        is_container_running("repom_postgres")

    assert excinfo.value.__cause__ is original


def test_start_service_prints_check_logs_hint_on_timeout(capsys):
    manager = MagicMock()
    manager.get_container_name.return_value = "repom_postgres"
    manager.start.side_effect = TimeoutError("PostgreSQL did not start within 30 seconds")

    with pytest.raises(SystemExit) as excinfo:
        start_service(lambda: manager, lambda: None)

    assert excinfo.value.code == 1
    assert "Check logs: docker logs repom_postgres" in capsys.readouterr().out


def test_start_service_prints_check_logs_hint_on_system_exit(capsys):
    """basekit's DockerManager.start() already catches a readiness TimeoutError
    itself, prints its own ERROR line, and calls sys.exit(1); start_service
    must still print the 'Check logs' hint in that case instead of letting
    SystemExit escape silently, and must not print the exception's bare
    "1" text on top of basekit's own error output."""
    manager = MagicMock()
    manager.get_container_name.return_value = "repom_postgres"
    manager.start.side_effect = SystemExit(1)

    with pytest.raises(SystemExit) as excinfo:
        start_service(lambda: manager, lambda: None)

    assert excinfo.value.code == 1
    out_lines = capsys.readouterr().out.splitlines()
    assert "Check logs: docker logs repom_postgres" in out_lines
    assert "1" not in out_lines
