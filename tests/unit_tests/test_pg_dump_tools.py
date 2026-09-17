from tests._init import *

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from _fake_pg_client import fake_client_command
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
    """The Docker custom-format dump must stream pg_dump's stdout straight
    into dump_path via the shared Popen-based streaming helper, never
    buffering the whole dump through DockerCommandExecutor.exec_command
    (repom#167) - only the small "--version" probe still goes through it."""
    dump_path = tmp_path / "db.dump"
    build_calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )

    def exec_command(container_name, command, stdin=None, capture_output=True):
        assert container_name == "managed-postgres"
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, b"pg_dump (PostgreSQL) 16.3\n", b"")
        raise AssertionError(f"exec_command must not carry the dump payload: {command}")

    def fake_build_pg_client_command(tool, **kwargs):
        build_calls.append((tool, kwargs))
        return fake_client_command()

    monkeypatch.setattr(pg_dump_tools.DockerCommandExecutor, "exec_command", exec_command)
    monkeypatch.setattr(pg_dump_tools, "build_pg_client_command", fake_build_pg_client_command)
    monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", str(1024 * 1024))

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is True
    assert result.tool_version == "pg_dump (PostgreSQL) 16.3"
    assert dump_path.stat().st_size == 1024 * 1024

    tool, kwargs = build_calls[-1]
    assert tool == "pg_dump"
    assert kwargs["container_name"] == "managed-postgres"
    assert kwargs["extra_args"] == ["--format=custom", "--no-owner", "--no-acl"]
    assert "--file" not in kwargs["extra_args"]
    assert "secret" not in repr(kwargs)


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
    """The Docker custom-format restore must stream dump_path's bytes
    straight into pg_restore's stdin via the shared Popen-based streaming
    helper, never buffering the whole dump through
    DockerCommandExecutor.exec_command (repom#167) - only the small
    "--version" probe still goes through it."""
    dump_path = tmp_path / "db.dump"
    payload = os.urandom(1024 * 1024)
    dump_path.write_bytes(payload)
    sink_path = tmp_path / "stdin_echo.bin"
    build_calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )

    def exec_command(container_name, command, stdin=None, capture_output=True):
        if command == ["pg_restore", "--version"]:
            return subprocess.CompletedProcess(command, 0, b"pg_restore (PostgreSQL) 16.3\n", b"")
        raise AssertionError(f"exec_command must not carry the restore payload: {command}")

    def fake_build_pg_client_command(tool, **kwargs):
        build_calls.append((tool, kwargs))
        return fake_client_command()

    monkeypatch.setattr(pg_dump_tools.DockerCommandExecutor, "exec_command", exec_command)
    monkeypatch.setattr(pg_dump_tools, "build_pg_client_command", fake_build_pg_client_command)
    monkeypatch.setenv("FAKE_CHILD_STDIN_SINK", str(sink_path))

    result = pg_restore_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is True
    assert sink_path.read_bytes() == payload

    tool, kwargs = build_calls[-1]
    assert tool == "pg_restore"
    assert kwargs["container_name"] == "managed-postgres"
    assert kwargs["extra_args"] == ["--clean", "--if-exists", "--no-owner", "--no-acl"]
    assert kwargs["stdin"] is True
    assert str(dump_path) not in repr(kwargs)


def _version_only_exec_command(tool_name):
    """A DockerCommandExecutor.exec_command stand-in that only answers the
    small "--version" probe and fails any call carrying a dump/restore
    payload, so a test using it proves that payload never reaches
    exec_command (repom#167)."""

    def exec_command(container_name, command, stdin=None, capture_output=True):
        if command == [tool_name, "--version"]:
            return subprocess.CompletedProcess(command, 0, b"", b"")
        raise AssertionError(f"exec_command must not carry the {tool_name} payload: {command}")

    return exec_command


def test_pg_dump_custom_via_docker_reports_missing_docker_binary(monkeypatch, tmp_path: Path):
    """A real FileNotFoundError from launching the Docker argv (docker CLI
    missing) is reported as returncode 127, and no dump file is left behind."""
    dump_path = tmp_path / "db.dump"

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor, "exec_command", _version_only_exec_command("pg_dump")
    )
    monkeypatch.setattr(
        pg_dump_tools,
        "build_pg_client_command",
        lambda tool, **kwargs: ["repom-test-nonexistent-pg-client-binary"],
    )

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 127
    assert result.used_docker is True
    assert not dump_path.exists()


def test_pg_restore_custom_via_docker_reports_missing_docker_binary(monkeypatch, tmp_path: Path):
    dump_path = tmp_path / "db.dump"
    dump_path.write_bytes(b"CUSTOM-DUMP")

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor, "exec_command", _version_only_exec_command("pg_restore")
    )
    monkeypatch.setattr(
        pg_dump_tools,
        "build_pg_client_command",
        lambda tool, **kwargs: ["repom-test-nonexistent-pg-client-binary"],
    )

    result = pg_restore_custom(_params(), dump_path)

    assert result.returncode == 127
    assert result.used_docker is True


def test_pg_restore_custom_via_docker_returns_result_when_child_exits_before_reading_all_stdin(
    monkeypatch, tmp_path: Path
):
    """When pg_restore stops reading stdin and exits with an error (repom#167
    review round 2) while a large dump is still being streamed in, this must
    return a PgToolResult with the child's real exit code and stderr instead
    of raising BrokenPipeError."""
    dump_path = tmp_path / "db.dump"
    dump_path.write_bytes(os.urandom(20 * 1024 * 1024))

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor, "exec_command", _version_only_exec_command("pg_restore")
    )
    monkeypatch.setattr(
        pg_dump_tools, "build_pg_client_command", lambda tool, **kwargs: fake_client_command()
    )
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "3")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "ERROR: relation does not exist\n")

    result = pg_restore_custom(_params(), dump_path)

    assert result.returncode == 3
    assert "relation does not exist" in result.stderr


def test_pg_dump_custom_via_docker_empty_output_removes_dump_file(monkeypatch, tmp_path: Path):
    dump_path = tmp_path / "db.dump"

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor, "exec_command", _version_only_exec_command("pg_dump")
    )
    monkeypatch.setattr(
        pg_dump_tools, "build_pg_client_command", lambda tool, **kwargs: fake_client_command()
    )
    monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", "0")

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 1
    assert "empty" in result.stderr
    assert not dump_path.exists()


def test_pg_dump_custom_via_docker_failure_after_partial_output_removes_dump_file(
    monkeypatch, tmp_path: Path
):
    """A pg_dump that writes some custom-format bytes and then fails must not
    leave a partial dump file at dump_path (repom#167 review round 2) -
    before this fix, only a fully successful dump avoided writing the file at
    all, but a mid-stream failure left dump_path holding a truncated dump."""
    dump_path = tmp_path / "db.dump"

    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor, "exec_command", _version_only_exec_command("pg_dump")
    )
    monkeypatch.setattr(
        pg_dump_tools, "build_pg_client_command", lambda tool, **kwargs: fake_client_command()
    )
    monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", "1024")
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "pg_dump: error: connection lost\n")

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 1
    assert not dump_path.exists()


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
