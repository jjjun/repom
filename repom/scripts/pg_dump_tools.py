"""Reusable PostgreSQL custom-format dump and restore helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from basekit.docker_manager import DockerCommandExecutor
from sqlalchemy.engine import make_url

from repom.config import RepomConfig, _is_local_postgres_host, config
from repom.docker_service import DockerUnavailableError, is_container_running
from repom.scripts._backup_utils import (
    ByteCountingWriter,
    build_host_pg_env,
    build_pg_client_command,
    checksum_path,
    compute_checksum,
    ensure_backup_dir,
    mask_password,
    open_backup_temp_file,
    run_postgres_via_docker_or_host,
    run_streaming_command,
    validate_backup_name_component,
    validate_client_database,
    warn_if_checksum_missing,
)
from repom.logging import ensure_logging_configured

VERSION_MISMATCH_HINT = (
    "Hint: PostgreSQL client/server versions appear to differ. Start the "
    "managed PostgreSQL container or install matching PostgreSQL client tools."
)
UNSUPPORTED_CLIENT_QUERY_PARAMETERS = {
    "host",
    "hostaddr",
    "service",
    "dsn",
    "port",
    "dbname",
    "database",
    "user",
    "password",
    # TLS and identity keys the client tools cannot carry safely: libpq would
    # honor them in the URL while the child process silently ignored them.
    # sslcert, sslkey, sslcrl, sslcrldir, channel_binding and
    # ssl_min_protocol_version are forwarded instead (PgConnParams.tls_options).
    "requiressl",
    "gssencmode",
    "options",
    "sslsni",
    "ssl_max_protocol_version",
    "sslcertmode",
    "sslnegotiation",
    "sslcompression",
    "sslpassword",
    "require_auth",
    "krbsrvname",
    "gsslib",
    "passfile",
    "servicefile",
    "target_session_attrs",
    "load_balance_hosts",
}


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
    use_docker: bool = True
    sslcert: str | None = None
    sslkey: str | None = None
    sslcrl: str | None = None
    sslcrldir: str | None = None
    channel_binding: str | None = None
    ssl_min_protocol_version: str | None = None

    def __post_init__(self) -> None:
        for name, value in self.tls_options.items():
            if any(char in value for char in "\0\r\n"):
                raise ValueError(
                    "PostgreSQL client tools reject a NUL byte or newline in the "
                    f"URL query value for: {name}"
                )

    def __repr__(self) -> str:
        password_display = "***" if self.password else "None"
        return (
            f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, "
            f"user={self.user!r}, password={password_display}, "
            f"database={self.database!r}, container_name={self.container_name!r}, "
            f"sslmode={self.sslmode!r}, sslrootcert={self.sslrootcert!r}, "
            f"use_docker={self.use_docker!r}, tls_options={self.tls_options!r})"
        )

    @property
    def tls_options(self) -> dict[str, str]:
        """TLS options beyond sslmode / sslrootcert that host client tools receive."""
        options = {
            "sslcert": self.sslcert,
            "sslkey": self.sslkey,
            "sslcrl": self.sslcrl,
            "sslcrldir": self.sslcrldir,
            "channel_binding": self.channel_binding,
            "ssl_min_protocol_version": self.ssl_min_protocol_version,
        }
        return {name: value for name, value in options.items() if value is not None}

    @classmethod
    def from_config(cls, config_obj: RepomConfig | None = None) -> "PgConnParams":
        """Build connection parameters from the active repom config."""
        active_config = config_obj or config
        if active_config.db_url_overridden:
            url = make_url(active_config.db_url)
            unsupported_overrides = UNSUPPORTED_CLIENT_QUERY_PARAMETERS.intersection(
                url.query
            )
            if unsupported_overrides:
                names = ", ".join(sorted(unsupported_overrides))
                raise ValueError(
                    "PostgreSQL client tools do not support URL query overrides for: "
                    f"{names}"
                )

            missing = [
                name
                for name, value in (
                    ("host", url.host),
                    ("user", url.username),
                    ("database", url.database),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "PostgreSQL client tools require a URL with "
                    f"{', '.join(missing)}; Unix-socket URLs are not supported."
                )

            def query_value(name: str) -> str | None:
                value = url.query.get(name)
                if isinstance(value, tuple):
                    return value[-1] if value else None
                return value

            params = cls(
                host=url.host,
                port=url.port if url.port is not None else 5432,
                user=url.username,
                password=url.password,
                database=url.database,
                container_name=active_config.postgres.container.get_container_name(),
                sslmode=query_value("sslmode"),
                sslrootcert=query_value("sslrootcert"),
                use_docker=False,
                sslcert=query_value("sslcert"),
                sslkey=query_value("sslkey"),
                sslcrl=query_value("sslcrl"),
                sslcrldir=query_value("sslcrldir"),
                channel_binding=query_value("channel_binding"),
                ssl_min_protocol_version=query_value("ssl_min_protocol_version"),
            )
            validate_client_database(params.database)
            return params

        tls = active_config.postgres_tls_settings()
        params = cls(
            host=active_config.postgres.host,
            port=active_config.postgres.port,
            user=active_config.postgres.user,
            password=active_config.postgres.password,
            database=active_config.postgres_db,
            container_name=active_config.postgres.container.get_container_name(),
            sslmode=tls.sslmode,
            sslrootcert=tls.sslrootcert,
            use_docker=_is_local_postgres_host(active_config.postgres.host),
        )
        validate_client_database(params.database)
        return params


@dataclass(frozen=True)
class PgToolResult:
    """Result for a PostgreSQL client-tool operation."""

    returncode: int
    used_docker: bool
    tool_version: str | None
    stderr: str


def pg_dump_custom(params: PgConnParams, dump_path: Path) -> PgToolResult:
    """Create a custom-format PostgreSQL dump."""

    ensure_logging_configured()
    dump_path = Path(dump_path)
    validate_backup_name_component(dump_path.name)
    if dump_path.drive and not dump_path.root:
        # A drive-relative path such as "C:_x.dump" (a database named "C:"
        # joined onto a directory) lands in the drive's working directory.
        raise ValueError(f"dump path cannot be drive-relative: {dump_path}")
    if not dump_path.parent.exists():
        # The directory is caller-supplied, so only one created here gets the
        # owner-only mode; an existing directory keeps its mode instead of being
        # chmod-ed (it may be shared or not owned by this process).
        ensure_backup_dir(dump_path.parent)
    partial_path = dump_path.with_name(f"{dump_path.name}.partial")
    checksum_destination = checksum_path(dump_path)
    checksum_partial_path = checksum_destination.with_name(
        f"{checksum_destination.name}.partial"
    )

    try:
        partial_file = open_backup_temp_file(partial_path)
    except OSError as exc:
        return PgToolResult(
            returncode=1,
            used_docker=False,
            tool_version=None,
            stderr=str(exc),
        )

    def dump_via_docker() -> PgToolResult:
        # Stream through the descriptor created above instead of reopening the
        # path, so a link swapped in after creation is never followed.
        with partial_file:
            return _pg_dump_custom_via_docker(params, partial_file)

    def dump_via_host() -> PgToolResult:
        # pg_dump opens --file itself; release the descriptor first.
        partial_file.close()
        return _pg_dump_custom_via_host(params, partial_path)

    checksum_partial_created = False
    try:
        result = run_postgres_via_docker_or_host(
            via_docker=dump_via_docker,
            via_host=dump_via_host,
            operation="custom-format dump",
            host_tools="host pg_dump",
            container_name=params.container_name,
            allow_docker=_allow_docker(params),
        )
        if result.returncode != 0:
            return result
        if not partial_path.exists() or partial_path.stat().st_size == 0:
            return PgToolResult(
                returncode=1,
                used_docker=result.used_docker,
                tool_version=result.tool_version,
                stderr="pg_dump produced empty custom-format output.",
            )

        try:
            checksum_file = open_backup_temp_file(checksum_partial_path)
            checksum_partial_created = True
            with checksum_file:
                checksum_file.write(
                    f"{compute_checksum(partial_path)}  {dump_path.name}\n".encode(
                        "utf-8"
                    )
                )
        except OSError as exc:
            return PgToolResult(
                returncode=1,
                used_docker=result.used_docker,
                tool_version=result.tool_version,
                stderr=str(exc),
            )
        partial_path.replace(dump_path)
        checksum_partial_path.replace(checksum_destination)
        return result
    finally:
        partial_file.close()
        partial_path.unlink(missing_ok=True)
        if checksum_partial_created:
            checksum_partial_path.unlink(missing_ok=True)


def pg_restore_custom(params: PgConnParams, dump_path: Path) -> PgToolResult:
    """Restore a custom-format PostgreSQL dump."""

    ensure_logging_configured()
    dump_path = Path(dump_path)
    warn_if_checksum_missing(dump_path)

    return run_postgres_via_docker_or_host(
        via_docker=lambda: _pg_restore_custom_via_docker(params, dump_path),
        via_host=lambda: _pg_restore_custom_via_host(params, dump_path),
        operation="custom-format restore",
        host_tools="host pg_restore",
        container_name=params.container_name,
        allow_docker=_allow_docker(params),
    )


def pg_tools_available(params: PgConnParams) -> bool:
    """Return True when Docker client tools or both host tools are available."""

    ensure_logging_configured()
    if _allow_docker(params):
        container_name = params.container_name or config.postgres.container.get_container_name()
        try:
            if is_container_running(container_name):
                return True
        except DockerUnavailableError:
            pass

    return shutil.which("pg_dump") is not None and shutil.which("pg_restore") is not None


def _allow_docker(params: PgConnParams) -> bool:
    # The container has no host environment, so TLS options that only reach the
    # child through it force the host client tools instead of docker exec.
    return (
        params.use_docker
        and not params.tls_options
        and _is_local_postgres_host(params.host)
    )


def _pg_dump_custom_via_docker(params: PgConnParams, dump_file: BinaryIO) -> PgToolResult:
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

    writer = ByteCountingWriter(dump_file)
    try:
        result = run_streaming_command(command, stdout_file=writer, password=params.password)
    except FileNotFoundError as exc:
        return PgToolResult(
            returncode=127,
            used_docker=True,
            tool_version=tool_version,
            stderr=mask_password(str(exc), params.password),
        )

    if result.returncode != 0:
        return PgToolResult(
            returncode=result.returncode,
            used_docker=True,
            tool_version=tool_version,
            stderr=_normalize_stderr(result.stderr, params.password),
        )

    if writer.bytes_written == 0:
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
        extra_args=["--clean", "--if-exists", "--no-owner", "--no-acl", "--single-transaction"],
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
        extra_args=[
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--single-transaction",
            "--",
            str(dump_path),
        ],
    )
    completed = _run_host_command(command, params)
    return PgToolResult(
        returncode=completed.returncode,
        used_docker=False,
        tool_version=tool_version,
        stderr=_normalize_stderr(completed.stderr, params.password),
    )


def _run_host_command(command: list[str], params: PgConnParams) -> subprocess.CompletedProcess:
    env = build_host_pg_env(
        params.password, params.sslmode, params.sslrootcert, params.tls_options
    )

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
