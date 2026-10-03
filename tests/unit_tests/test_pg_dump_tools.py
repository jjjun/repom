import pytest

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from _fake_pg_client import fake_client_command
from repom.config import RepomConfig
from repom.scripts import _backup_utils, pg_dump_tools
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
    host: str = "localhost",
) -> PgConnParams:
    return PgConnParams(
        host=host,
        port=5435,
        user="user",
        password=password,
        database="mine_py",
        container_name="managed-postgres",
        sslmode=sslmode,
        sslrootcert=sslrootcert,
    )


def test_pg_conn_params_from_overridden_url():
    config = RepomConfig()
    config.db_url = (
        "postgresql+psycopg://url_user:url_password@db.example.internal:5544/url_db"
        "?sslmode=verify-full&sslrootcert=%2Ftmp%2Fca.pem"
    )

    params = PgConnParams.from_config(config)

    assert params.host == "db.example.internal"
    assert params.port == 5544
    assert params.user == "url_user"
    assert params.password == "url_password"
    assert params.database == "url_db"
    assert params.sslmode == "verify-full"
    assert params.sslrootcert == "/tmp/ca.pem"
    assert params.use_docker is False
    assert "url_password" not in repr(params)


def test_pg_conn_params_from_config_keeps_structured_settings():
    config = RepomConfig()
    config.db_type = "postgres"
    config.postgres.host = "127.0.0.1"
    config.postgres.port = 5543
    config.postgres.user = "configured-user"
    config.postgres.password = "configured-password"
    config.postgres.database = "configured-db"

    params = PgConnParams.from_config(config)

    assert params.host == "127.0.0.1"
    assert params.port == 5543
    assert params.user == "configured-user"
    assert params.password == "configured-password"
    assert params.database == "configured-db"
    assert params.use_docker is True


@pytest.mark.parametrize("host", ["", "/var/run/postgresql", "127.0.0.1", "localhost"])
def test_pg_conn_params_enables_docker_for_local_configured_hosts(host):
    config = RepomConfig()
    config.db_type = "postgres"
    config.postgres.host = host

    assert PgConnParams.from_config(config).use_docker is True


def test_pg_conn_params_disables_docker_for_remote_configured_host():
    config = RepomConfig()
    config.db_type = "postgres"
    config.postgres.host = "db.example.internal"

    assert PgConnParams.from_config(config).use_docker is False


@pytest.mark.parametrize("destination_option", ["host", "hostaddr", "service", "dsn"])
def test_pg_conn_params_rejects_url_destination_query_overrides(destination_option):
    config = RepomConfig()
    config.db_url = (
        "postgresql://url_user@db.example.internal/url_db"
        f"?{destination_option}=other.example.internal"
    )

    with pytest.raises(ValueError, match="destination overrides"):
        PgConnParams.from_config(config)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://url_user:url_password@/url_db?host=/var/run/postgresql",
        "postgresql://db.example.internal/url_db",
        "postgresql://url_user@db.example.internal/",
    ],
)
def test_pg_conn_params_rejects_urls_without_host_user_or_database(url):
    config = RepomConfig()
    config.db_url = url

    with pytest.raises(ValueError, match="require a URL with"):
        PgConnParams.from_config(config)


def test_pg_conn_params_uses_default_postgres_port():
    config = RepomConfig()
    config.db_url = "postgresql://url_user:url_password@db.example.internal/url_db"

    assert PgConnParams.from_config(config).port == 5432


def test_pg_dump_custom_uses_docker_stdout_without_file(monkeypatch, tmp_path: Path):
    """The Docker custom-format dump must stream pg_dump's stdout straight
    into dump_path via the shared Popen-based streaming helper, never
    buffering the whole dump through DockerCommandExecutor.exec_command
    (repom#167) - only the small "--version" probe still goes through it."""
    dump_path = tmp_path / "db.dump"
    build_calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        _backup_utils,
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
    assert _backup_utils.verify_checksum(dump_path) is True
    assert list(tmp_path.glob("*.partial")) == []
    if os.name == "posix":
        assert dump_path.stat().st_mode & 0o777 == 0o600

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
        _backup_utils,
        "is_container_running",
        MagicMock(return_value=False),
    )

    def fake_run(command, **kwargs):
        run_calls.append((command, kwargs))
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 16.3\n", "")
        assert kwargs["env"]["PGPASSWORD"] == "secret"
        Path(command[-1]).write_bytes(b"CUSTOM-DUMP")
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
        str(dump_path.with_name(f"{dump_path.name}.partial")),
    ]
    assert "secret" not in command
    assert dump_path.read_bytes() == b"CUSTOM-DUMP"
    assert _backup_utils.verify_checksum(dump_path) is True
    assert not dump_path.with_name(f"{dump_path.name}.partial").exists()


def test_pg_dump_custom_uses_host_tools_for_remote_host_even_if_docker_is_enabled(
    monkeypatch, tmp_path
):
    dump_path = tmp_path / "db.dump"
    params = _params(host="db.example.internal")
    is_container_running = MagicMock(return_value=True)

    def dump_via_host(_params, partial_path):
        partial_path.write_bytes(b"CUSTOM-DUMP")
        return pg_dump_tools.PgToolResult(0, False, None, "")

    monkeypatch.setattr(_backup_utils, "is_container_running", is_container_running)
    monkeypatch.setattr(pg_dump_tools, "_pg_dump_custom_via_host", dump_via_host)
    docker_dump = MagicMock(side_effect=AssertionError("remote host must use host tools"))
    monkeypatch.setattr(pg_dump_tools, "_pg_dump_custom_via_docker", docker_dump)

    result = pg_dump_custom(params, dump_path)

    assert result.returncode == 0
    assert result.used_docker is False
    assert dump_path.read_bytes() == b"CUSTOM-DUMP"
    is_container_running.assert_not_called()
    docker_dump.assert_not_called()


def test_pg_dump_custom_checksum_partial_failure_preserves_existing_file(
    monkeypatch, tmp_path
):
    dump_path = tmp_path / "db.dump"
    checksum_partial_path = tmp_path / "db.dump.sha256.partial"
    checksum_partial_path.write_bytes(b"stale checksum partial")

    def dump_via_host(_params, partial_path):
        partial_path.write_bytes(b"CUSTOM-DUMP")
        return pg_dump_tools.PgToolResult(0, False, None, "")

    monkeypatch.setattr(pg_dump_tools, "_pg_dump_custom_via_host", dump_via_host)

    result = pg_dump_custom(_params(host="db.example.internal"), dump_path)

    assert result.returncode == 1
    assert "File exists" in result.stderr
    assert checksum_partial_path.read_bytes() == b"stale checksum partial"
    assert not dump_path.exists()
    assert not dump_path.with_name(f"{dump_path.name}.partial").exists()


@pytest.mark.skipif(os.name != "posix", reason="symbolic-link behavior is POSIX-specific")
def test_pg_dump_custom_replaces_symlink_without_following_it(monkeypatch, tmp_path):
    dump_path = tmp_path / "db.dump"
    victim_path = tmp_path / "victim.dump"
    victim_path.write_bytes(b"keep this file")
    dump_path.symlink_to(victim_path)

    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=True))
    monkeypatch.setattr(
        pg_dump_tools.DockerCommandExecutor,
        "exec_command",
        _version_only_exec_command("pg_dump"),
    )
    monkeypatch.setattr(
        pg_dump_tools,
        "build_pg_client_command",
        lambda tool, **kwargs: fake_client_command(),
    )
    monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", "64")

    result = pg_dump_custom(_params(), dump_path)

    assert result.returncode == 0
    assert not dump_path.is_symlink()
    assert victim_path.read_bytes() == b"keep this file"
    assert _backup_utils.verify_checksum(dump_path) is True


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
        _backup_utils,
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
    assert kwargs["extra_args"] == [
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--single-transaction",
    ]
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
        _backup_utils,
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
        _backup_utils,
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
        _backup_utils,
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
        _backup_utils,
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
    assert not dump_path.with_name(f"{dump_path.name}.partial").exists()


def test_pg_dump_custom_via_docker_failure_after_partial_output_removes_dump_file(
    monkeypatch, tmp_path: Path
):
    """A pg_dump that writes some custom-format bytes and then fails must not
    leave a partial dump file at dump_path (repom#167 review round 2) -
    before this fix, only a fully successful dump avoided writing the file at
    all, but a mid-stream failure left dump_path holding a truncated dump."""
    dump_path = tmp_path / "db.dump"

    monkeypatch.setattr(
        _backup_utils,
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
    assert not dump_path.with_name(f"{dump_path.name}.partial").exists()


def test_pg_tools_available_returns_true_when_only_container_available(monkeypatch):
    monkeypatch.setattr(
        pg_dump_tools,
        "is_container_running",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(pg_dump_tools.shutil, "which", lambda name: None)

    assert pg_tools_available(_params()) is True


def test_pg_tools_available_falls_back_to_host_tools_when_docker_daemon_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        pg_dump_tools,
        "is_container_running",
        MagicMock(
            side_effect=pg_dump_tools.DockerUnavailableError(
                "docker is unavailable: Cannot connect to the Docker daemon"
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
        _backup_utils,
        "is_container_running",
        MagicMock(
            side_effect=pg_dump_tools.DockerUnavailableError(
                "docker is unavailable: Cannot connect to the Docker daemon"
            )
        ),
    )

    def fake_run(command, **kwargs):
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 16.3\n", "")
        Path(command[-1]).write_bytes(b"CUSTOM-DUMP")
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
    commands = []

    monkeypatch.setattr(
        _backup_utils,
        "is_container_running",
        MagicMock(
            side_effect=pg_dump_tools.DockerUnavailableError(
                "docker is unavailable: Cannot connect to the Docker daemon"
            )
        ),
    )

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["pg_restore", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_restore (PostgreSQL) 16.3\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pg_dump_tools.subprocess, "run", fake_run)

    result = pg_restore_custom(_params(), dump_path)

    assert result.returncode == 0
    assert result.used_docker is False
    assert commands[-1][-6:] == [
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--single-transaction",
        str(dump_path),
    ]


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
        _backup_utils,
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
        _backup_utils,
        "is_container_running",
        MagicMock(return_value=False),
    )

    def fake_run(command, **kwargs):
        run_calls.append((command, kwargs))
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 16.3\n", "")
        Path(command[-1]).write_bytes(b"CUSTOM-DUMP")
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
        _backup_utils,
        "is_container_running",
        MagicMock(return_value=False),
    )

    def fake_run(command, **kwargs):
        run_calls.append((command, kwargs))
        if command == ["pg_dump", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pg_dump (PostgreSQL) 16.3\n", "")
        Path(command[-1]).write_bytes(b"CUSTOM-DUMP")
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
