"""Reusable PostgreSQL custom-format dump and restore helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from basekit.docker_manager import DockerCommandExecutor

from repom.config import config
from repom.scripts._backup_utils import run_postgres_via_docker_or_host

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
    password: str | None
    database: str
    container_name: str | None = None

    @classmethod
    def from_config(cls) -> "PgConnParams":
        """Build connection parameters from the active repom config."""
        return cls(
            host=config.postgres.host,
            port=config.postgres.port,
            user=config.postgres.user,
            password=config.postgres.password,
            database=config.postgres_db,
            container_name=config.postgres.container.get_container_name(),
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
        if DockerCommandExecutor.is_container_running(container_name):
            return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return shutil.which("pg_dump") is not None and shutil.which("pg_restore") is not None


def _pg_dump_custom_via_docker(params: PgConnParams, dump_path: Path) -> PgToolResult:
    container_name = _container_name(params)
    tool_version = _docker_tool_version(container_name, "pg_dump", params.password)
    command = _docker_pg_dump_command(params)

    try:
        completed = DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=command,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        return PgToolResult(
            returncode=127,
            used_docker=True,
            tool_version=tool_version,
            stderr=_sanitize_stderr(str(exc), params.password),
        )
    except subprocess.CalledProcessError as exc:
        return PgToolResult(
            returncode=exc.returncode,
            used_docker=True,
            tool_version=tool_version,
            stderr=_normalize_stderr(exc.stderr, params.password),
        )

    stdout = completed.stdout or b""
    if not stdout:
        return PgToolResult(
            returncode=1,
            used_docker=True,
            tool_version=tool_version,
            stderr="pg_dump produced empty custom-format output.",
        )

    dump_path.write_bytes(stdout)
    return PgToolResult(
        returncode=completed.returncode,
        used_docker=True,
        tool_version=tool_version,
        stderr=_normalize_stderr(completed.stderr, params.password),
    )


def _pg_dump_custom_via_host(params: PgConnParams, dump_path: Path) -> PgToolResult:
    tool_version = _host_tool_version("pg_dump", params.password)
    command = _host_pg_dump_command(params, dump_path)
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
    command = _docker_pg_restore_command(params)

    try:
        completed = DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=command,
            stdin=dump_path.read_bytes(),
            capture_output=True,
        )
    except FileNotFoundError as exc:
        return PgToolResult(
            returncode=127,
            used_docker=True,
            tool_version=tool_version,
            stderr=_sanitize_stderr(str(exc), params.password),
        )
    except subprocess.CalledProcessError as exc:
        return PgToolResult(
            returncode=exc.returncode,
            used_docker=True,
            tool_version=tool_version,
            stderr=_normalize_stderr(exc.stderr, params.password),
        )

    return PgToolResult(
        returncode=completed.returncode,
        used_docker=True,
        tool_version=tool_version,
        stderr=_normalize_stderr(completed.stderr, params.password),
    )


def _pg_restore_custom_via_host(params: PgConnParams, dump_path: Path) -> PgToolResult:
    tool_version = _host_tool_version("pg_restore", params.password)
    command = _host_pg_restore_command(params, dump_path)
    completed = _run_host_command(command, params)
    return PgToolResult(
        returncode=completed.returncode,
        used_docker=False,
        tool_version=tool_version,
        stderr=_normalize_stderr(completed.stderr, params.password),
    )


def _run_host_command(command: list[str], params: PgConnParams) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if params.password is not None:
        env["PGPASSWORD"] = params.password

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


def _host_pg_dump_command(params: PgConnParams, dump_path: Path) -> list[str]:
    return [
        "pg_dump",
        "-h",
        params.host,
        "-p",
        str(params.port),
        "-U",
        params.user,
        "-d",
        params.database,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(dump_path),
    ]


def _docker_pg_dump_command(params: PgConnParams) -> list[str]:
    return [
        "pg_dump",
        "-U",
        params.user,
        "-d",
        params.database,
        "--format=custom",
        "--no-owner",
        "--no-acl",
    ]


def _host_pg_restore_command(params: PgConnParams, dump_path: Path) -> list[str]:
    return [
        "pg_restore",
        "-h",
        params.host,
        "-p",
        str(params.port),
        "-U",
        params.user,
        "-d",
        params.database,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        str(dump_path),
    ]


def _docker_pg_restore_command(params: PgConnParams) -> list[str]:
    return [
        "pg_restore",
        "-U",
        params.user,
        "-d",
        params.database,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
    ]


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
    if password:
        return stderr.replace(password, "***")
    return stderr


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
