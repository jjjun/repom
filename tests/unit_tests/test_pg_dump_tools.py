from tests._init import *

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from repom.config import RepomConfig
from repom.scripts import pg_dump_tools
from repom.scripts.pg_dump_tools import (
    PgConnParams,
    pg_dump_custom,
    pg_restore_custom,
    pg_tools_available,
)


def _params(
    password: str | None = "secret",
    sslmode: str | None = None,
    sslrootcert: str | None = None,
) -> PgConnParams:
    return PgConnParams(
        host="localhost",
        port=5435,
        user="user",
        password=password,
        database="mine_py",
        container_name="managed-postgres",
        sslmode=sslmode,
        sslrootcert=sslrootcert,
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


def test_pg_tools_available_falls_back_to_host_tools_when_docker_daemon_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                1,
                ["docker", "ps"],
                stderr="Cannot connect to the Docker daemon",
            )
        ),
    )
    monkeypatch.setattr(pg_dump_tools.shutil, "which", lambda name: f"/usr/bin/{name}")

    assert pg_tools_available(_params()) is True


def test_pg_dump_custom_falls_back_to_host_when_docker_daemon_unavailable(
    monkeypatch, tmp_path: Path
):
    dump_path = tmp_path / "db.dump"

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                1,
                ["docker", "ps"],
                stderr="Cannot connect to the Docker daemon",
            )
        ),
    )

    def fake_run(command, **kwargs):
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 16.3\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is False


def test_pg_restore_custom_falls_back_to_host_when_docker_daemon_unavailable(
    monkeypatch, tmp_path: Path
):
    dump_path = tmp_path / "db.dump"
    dump_path.write_bytes(b"CUSTOM-DUMP")

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                1,
                ["docker", "ps"],
                stderr="Cannot connect to the Docker daemon",
            )
        ),
    )

    def fake_run(command, **kwargs):
        if command == ["pg_restore", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_restore (PostgreSQL) 16.3\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    result = pg_restore_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is False


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


def test_pg_conn_params_repr_includes_tls_fields():
    params = _params(sslmode="verify-full", sslrootcert="/etc/ssl/certs/test-ca.pem")

    text = repr(params)

    assert "sslmode='verify-full'" in text
    assert "sslrootcert='/etc/ssl/certs/test-ca.pem'" in text
    assert "secret" not in text


def test_pg_dump_custom_via_host_passes_tls_settings_in_env(monkeypatch, tmp_path: Path):
    dump_path = tmp_path / "db.dump"
    params = _params(sslmode="verify-full", sslrootcert="/etc/ssl/certs/test-ca.pem")
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
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    pg_dump_custom(params, dump_path)

    command, kwargs = run_calls[-1]
    assert kwargs["env"]["PGSSLMODE"] == "verify-full"
    assert kwargs["env"]["PGSSLROOTCERT"] == "/etc/ssl/certs/test-ca.pem"
    assert "verify-full" not in command


def test_pg_dump_custom_via_host_leaves_inherited_sslmode_untouched_without_tls_fields(
    monkeypatch, tmp_path: Path
):
    """directly constructed PgConnParams without sslmode/sslrootcert leaves the
    inherited libpq environment untouched (compatibility for direct construction)."""
    monkeypatch.setenv("PGSSLMODE", "disable")
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
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    pg_dump_custom(_params(), dump_path)

    command, kwargs = run_calls[-1]
    assert kwargs["env"]["PGSSLMODE"] == "disable"
    assert "PGSSLROOTCERT" not in kwargs["env"]


class TestPgConnParamsFromConfig:
    """PgConnParams.from_config() は RepomConfig.postgres_tls_settings() を共有する"""

    def _cfg(self, exec_env="dev", host="localhost", sslmode=None, sslrootcert=None):
        cfg = RepomConfig(exec_env=exec_env)
        cfg.db_type = "postgres"
        cfg.postgres.host = host
        cfg.postgres.sslmode = sslmode
        cfg.postgres.sslrootcert = sslrootcert
        return cfg

    def test_local_default_uses_prefer(self, monkeypatch):
        monkeypatch.setattr(pg_dump_tools, "config", self._cfg(host="localhost"))

        params = PgConnParams.from_config()

        assert params.sslmode == "prefer"
        assert params.sslrootcert is None

    def test_remote_prod_default_uses_require(self, monkeypatch):
        monkeypatch.setattr(
            pg_dump_tools, "config", self._cfg(exec_env="prod", host="db.example.com")
        )

        params = PgConnParams.from_config()

        assert params.sslmode == "require"

    def test_explicit_verify_full_and_sslrootcert(self, monkeypatch):
        monkeypatch.setattr(
            pg_dump_tools,
            "config",
            self._cfg(
                exec_env="prod",
                host="db.example.com",
                sslmode="verify-full",
                sslrootcert="/etc/ssl/certs/test-ca.pem",
            ),
        )

        params = PgConnParams.from_config()

        assert params.sslmode == "verify-full"
        assert params.sslrootcert == "/etc/ssl/certs/test-ca.pem"

    def test_remote_prod_weak_sslmode_raises_before_process(self, monkeypatch):
        monkeypatch.setattr(
            pg_dump_tools,
            "config",
            self._cfg(exec_env="prod", host="db.example.com", sslmode="prefer"),
        )

        with pytest.raises(ValueError, match="sslmode"):
            PgConnParams.from_config()
