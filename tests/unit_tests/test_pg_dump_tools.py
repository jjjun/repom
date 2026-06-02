from tests._init import *

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from repom.scripts import pg_dump_tools
from repom.scripts.pg_dump_tools import (
    PgConnParams,
    pg_dump_custom,
    pg_restore_custom,
    pg_tools_available,
)


def _params(password: str | None = "secret") -> PgConnParams:
    return PgConnParams(
        host="localhost",
        port=5435,
        user="user",
        password=password,
        database="mine_py",
        container_name="managed-postgres",
    )


def test_pg_dump_custom_uses_docker_stdout_without_file(monkeypatch, tmp_path: Path):
    dump_path = tmp_path / "db.dump"
    calls: list[list[str]] = []

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )

    def exec_command(container_name, command, stdin=None, capture_output=True):
        calls.append(command)
        assert container_name == "managed-postgres"
        assert stdin is None
        assert capture_output is True
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, b"pg_dump (PostgreSQL) 16.3\n", b"")
        return subprocess.CompletedProcess(command, 0, b"CUSTOM-DUMP", b"")

    monkeypatch.setattr(pg_dump_tools.DockerCommandExecutor, "exec_command", exec_command)

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is True
    assert result.tool_version == "pg_dump (PostgreSQL) 16.3"
    assert dump_path.read_bytes() == b"CUSTOM-DUMP"
    assert calls[-1] == [
        "pg_dump",
        "-U",
        "user",
        "-d",
        "mine_py",
        "--format=custom",
        "--no-owner",
        "--no-acl",
    ]
    assert "--file" not in calls[-1]
    assert "secret" not in calls[-1]


def test_pg_dump_custom_uses_host_file_when_container_stopped(monkeypatch, tmp_path: Path):
    dump_path = tmp_path / "db.dump"
    run_calls = []

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=False),
    )

    def fake_run(command, **kwargs):
        run_calls.append((command, kwargs))
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 16.3\n", "")
        assert kwargs["env"]["PGPASSWORD"] == "secret"
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is False
    command = run_calls[-1][0]
    assert command == [
        "pg_dump",
        "-h",
        "localhost",
        "-p",
        "5435",
        "-U",
        "user",
        "-d",
        "mine_py",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(dump_path),
    ]
    assert "secret" not in command


def test_pg_restore_custom_streams_dump_bytes_to_docker(monkeypatch, tmp_path: Path):
    dump_path = tmp_path / "db.dump"
    dump_path.write_bytes(b"CUSTOM-DUMP")
    restore_stdin = None
    restore_command = None

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )

    def exec_command(container_name, command, stdin=None, capture_output=True):
        nonlocal restore_stdin, restore_command
        if command == ["pg_restore", "--version"]:
            return subprocess.CompletedProcess(command, 0, b"pg_restore (PostgreSQL) 16.3\n", b"")
        restore_stdin = stdin
        restore_command = command
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(pg_dump_tools.DockerCommandExecutor, "exec_command", exec_command)

    result = pg_restore_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is True
    assert restore_stdin == b"CUSTOM-DUMP"
    assert restore_command == [
        "pg_restore",
        "-U",
        "user",
        "-d",
        "mine_py",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
    ]
    assert str(dump_path) not in restore_command


def test_pg_tools_available_returns_true_when_only_container_available(monkeypatch):
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(pg_dump_tools.shutil, "which", lambda name: None)

    assert pg_tools_available(_params()) is True


def test_pg_tool_result_redacts_password_and_adds_version_mismatch_hint(
    monkeypatch,
    tmp_path: Path,
):
    dump_path = tmp_path / "db.dump"
    mismatch = (
        "pg_dump: error: server version: 16.3; "
        "pg_dump version: 13.4; password secret"
    )

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=False),
    )

    def fake_run(command, **kwargs):
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 13.4\n", "")
        return subprocess.CompletedProcess(command, 1, "", mismatch)

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 1
    assert "secret" not in result.stderr
    assert "***" in result.stderr
    assert "matching PostgreSQL client tools" in result.stderr
