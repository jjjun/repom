"""Reusable PostgreSQL custom-format dump and restore helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from basekit.docker_manager import DockerCommandExecutor

from repom.config import config
from repom.docker_service import DockerUnavailableError, is_container_running
from repom.scripts._backup_utils import (
    ByteCountingWriter,
    build_host_pg_env,
    build_pg_client_command,
    mask_password,
    run_postgres_via_docker_or_host,
    run_streaming_command,
)

VERSION_MISMATCH_HINT = (
    "Hint: PostgreSQL client/server versions appear to differ. Start the "
    "managed PostgreSQL container or install matching PostgreSQL client tools."
)


@dataclass(frozen=True)
class PgConnParams:
    """Connection details for PostgreSQL client tools."""

    host: str
    port: int
    user: str
    password: str | None = field(repr=False)
    database: str
    container_name: str | None = None
    sslmode: str | None = None
    sslrootcert: str | None = None

    def __repr__(self) -> str:
        password_display = "***" if self.password else "None"
        return (
            f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, "
            f"user={self.user!r}, password={password_display}, "
            f"database={self.database!r}, container_name={self.container_name!r}, "
            f"sslmode={self.sslmode!r}, sslrootcert={self.sslrootcert!r})"
        )

    @classmethod
    def from_config(cls) -> "PgConnParams":
        """Build connection parameters from the active repom config."""
        tls = config.postgres_tls_settings()
        return cls(
            host=config.postgres.host,
            port=config.postgres.port,
            user=config.postgres.user,
            password=config.postgres.password,
            database=config.postgres_db,
            container_name=config.postgres.container.get_container_name(),
            sslmode=tls.sslmode,
            sslrootcert=tls.sslrootcert,
        )


@dataclass(frozen=True)
class PgToolResult:
    """Result for a PostgreSQL client-tool operation."""

    returncode: int
    used_docker: bool
    tool_version: str | None
    stderr: str


def pg_dump_custom(params: PgConnParams, dump_path: Path) -> PgToolResult:
    """Create a custom-format PostgreSQL dump."""

    dump_path = Path(dump_path)
    dump_path.parent.mkdir(parents=True, exist_ok=True)

    return run_postgres_via_docker_or_host(
        via_docker=lambda: _pg_dump_custom_via_docker(params, dump_path),
        via_host=lambda: _pg_dump_custom_via_host(params, dump_path),
        operation="custom-format dump",
        host_tools="host pg_dump",
        container_name=params.container_name,
    )


def pg_restore_custom(params: PgConnParams, dump_path: Path) -> PgToolResult:
    """Restore a custom-format PostgreSQL dump."""

    dump_path = Path(dump_path)

    return run_postgres_via_docker_or_host(
        via_docker=lambda: _pg_restore_custom_via_docker(params, dump_path),
        via_host=lambda: _pg_restore_custom_via_host(params, dump_path),
        operation="custom-format restore",
        host_tools="host pg_restore",
        container_name=params.container_name,
    )


def pg_tools_available(params: PgConnParams) -> bool:
    """Return True when Docker client tools or both host tools are available."""

    container_name = params.container_name or config.postgres.container.get_container_name()
    try:
        if is_container_running(container_name):
            return True
    except DockerUnavailableError:
        pass

    return shutil.which("pg_dump") is not None and shutil.which("pg_restore") is not None


def _pg_dump_custom_via_docker(params: PgConnParams, dump_path: Path) -> PgToolResult:
    container_name = _container_name(params)
    tool_version = _docker_tool_version(container_name, "pg_dump", params.password)
    command = build_pg_client_command(
        "pg_dump",
        host=params.host,
        port=params.port,
        user=params.user,
        database=params.database,
        extra_args=["--format=custom", "--no-owner", "--no-acl"],
        container_name=container_name,
    )

    try:
        with open(dump_path, "wb") as dump_file:
            writer = ByteCountingWriter(dump_file)
            result = run_streaming_command(command, stdout_file=writer, password=params.password)
    except FileNotFoundError as exc:
        dump_path.unlink(missing_ok=True)
        return PgToolResult(
            returncode=127,
            used_docker=True,
            tool_version=tool_version,
            stderr=mask_password(str(exc), params.password),
        )

    if result.returncode != 0:
        dump_path.unlink(missing_ok=True)
        return PgToolResult(
            returncode=result.returncode,
            used_docker=True,
            tool_version=tool_version,
            stderr=_normalize_stderr(result.stderr, params.password),
        )

    if writer.bytes_written == 0:
        dump_path.unlink(missing_ok=True)
        return PgToolResult(
            returncode=1,
            used_docker=True,
            tool_version=tool_version,
            stderr="pg_dump produced empty custom-format output.",
        )

    return PgToolResult(
        returncode=result.returncode,
        used_docker=True,
        tool_version=tool_version,
        stderr=_normalize_stderr(result.stderr, params.password),
    )


def _pg_dump_custom_via_host(params: PgConnParams, dump_path: Path) -> PgToolResult:
    tool_version = _host_tool_version("pg_dump", params.password)
    command = build_pg_client_command(
        "pg_dump",
        host=params.host,
        port=params.port,
        user=params.user,
        database=params.database,
        extra_args=["--format=custom", "--no-owner", "--no-acl", "--file", str(dump_path)],
    )
    completed = _run_host_command(command, params)
    return PgToolResult(
        returncode=completed.returncode,
        used_docker=False,
        tool_version=tool_version,
        stderr=_normalize_stderr(completed.stderr, params.password),
    )


def _pg_restore_custom_via_docker(params: PgConnParams, dump_path: Path) -> PgToolResult:
    container_name = _container_name(params)
    tool_version = _docker_tool_version(container_name, "pg_restore", params.password)
    command = build_pg_client_command(
        "pg_restore",
        host=params.host,
        port=params.port,
        user=params.user,
        database=params.database,
        extra_args=["--clean", "--if-exists", "--no-owner", "--no-acl"],
        container_name=container_name,
        stdin=True,
    )

    try:
        with open(dump_path, "rb") as dump_file:
            result = run_streaming_command(command, stdin_file=dump_file, password=params.password)
    except FileNotFoundError as exc:
        return PgToolResult(
            returncode=127,
            used_docker=True,
            tool_version=tool_version,
            stderr=mask_password(str(exc), params.password),
        )

    return PgToolResult(
        returncode=result.returncode,
        used_docker=True,
        tool_version=tool_version,
        stderr=_normalize_stderr(result.stderr, params.password),
    )


def _pg_restore_custom_via_host(params: PgConnParams, dump_path: Path) -> PgToolResult:
    tool_version = _host_tool_version("pg_restore", params.password)
    command = build_pg_client_command(
        "pg_restore",
        host=params.host,
        port=params.port,
        user=params.user,
        database=params.database,
        extra_args=["--clean", "--if-exists", "--no-owner", "--no-acl", str(dump_path)],
    )
    completed = _run_host_command(command, params)
    return PgToolResult(
        returncode=completed.returncode,
        used_docker=False,
        tool_version=tool_version,
        stderr=_normalize_stderr(completed.stderr, params.password),
    )


def _run_host_command(command: list[str], params: PgConnParams) -> subprocess.CompletedProcess:
    env = build_host_pg_env(params.password, params.sslmode, params.sslrootcert)

    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))


def _docker_tool_version(
    container_name: str,
    tool_name: str,
    password: str | None,
) -> str | None:
    try:
        completed = DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=[tool_name, "--version"],
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return _first_text_line(completed.stdout, password)


def _host_tool_version(tool_name: str, password: str | None) -> str | None:
    try:
        completed = subprocess.run(
            [tool_name, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    return _first_text_line(completed.stdout, password)


def _first_text_line(value: bytes | str | None, password: str | None) -> str | None:
    text = _decode_output(value)
    if not text:
        return None
    return _sanitize_stderr(text.splitlines()[0], password)


def _normalize_stderr(value: bytes | str | None, password: str | None) -> str:
    stderr = _sanitize_stderr(_decode_output(value), password)
    if _looks_like_version_mismatch(stderr) and VERSION_MISMATCH_HINT not in stderr:
        if stderr and not stderr.endswith("\n"):
            stderr = f"{stderr}\n"
        stderr = f"{stderr}{VERSION_MISMATCH_HINT}"
    return stderr


def _sanitize_stderr(stderr: str, password: str | None) -> str:
    return mask_password(stderr, password)


def _decode_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return value.strip()


def _looks_like_version_mismatch(stderr: str) -> bool:
    lower = stderr.lower()
    return "server version" in lower and (
        "pg_dump version" in lower
        or "pg_restore version" in lower
        or "aborting because of server version mismatch" in lower
    )


def _container_name(params: PgConnParams) -> str:
    return params.container_name or config.postgres.container.get_container_name()
