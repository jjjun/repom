from pathlib import Path
from dataclasses import dataclass
import errno
import gzip
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from typing import BinaryIO, Callable, Optional, Sequence, TypeVar

from repom.config import config
from repom.docker_service import DockerUnavailableError, is_container_running
from repom.logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")
STALE_PARTIAL_BACKUP_AGE_SECONDS = 24 * 60 * 60

# Cap the buffered stderr size accumulated while draining a child process's
# stderr on a background thread (see run_streaming_command); a client tool
# emitting more than this spills to a temp file instead of growing memory.
STREAMED_STDERR_SPOOL_LIMIT = 1024 * 1024

# Backup artifacts hold a full copy of the database; keep them readable only
# by the owner so a second local account or unprivileged process cannot read
# them off disk.
BACKUP_DIR_MODE = 0o700
BACKUP_FILE_MODE = 0o600
CHECKSUM_SUFFIX = ".sha256"


class ChecksumError(Exception):
    """Raised when a backup file does not match its recorded checksum."""


class BackupError(RuntimeError):
    """Raised when a backup operation fails, after any partial file is removed."""


class RestoreError(RuntimeError):
    """Raised when a restore operation fails, after any partial file is removed."""


def ensure_backup_dir(backup_dir: str | Path) -> Path:
    """Create ``backup_dir`` if missing and enforce mode 0700.

    Applied on every call, not only on first creation, so a pre-existing and
    more permissive directory is tightened the next time a backup runs.
    """
    path = Path(backup_dir)
    path.mkdir(mode=BACKUP_DIR_MODE, parents=True, exist_ok=True)
    os.chmod(path, BACKUP_DIR_MODE)
    return path


def open_backup_temp_file(path: Path) -> BinaryIO:
    """Create a new backup temp file with mode 0600 from creation.

    Uses O_EXCL so a concurrent or leftover write at ``path`` is never
    silently truncated and reused with looser permissions.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, BACKUP_FILE_MODE)
    return os.fdopen(fd, "wb")


def sqlite_source_uri(path: Path, mode: str = "ro", *, immutable: bool = False) -> str:
    """Return a SQLite URI opening ``path`` in ``mode`` without creating it.

    ``sqlite3.connect()`` silently creates a missing file as a new empty
    database; connecting through this URI instead makes a missing source
    surface as sqlite3.OperationalError.

    ``immutable`` tells SQLite the file will not change while open, so a
    WAL-flagged file can be read without SQLite creating -shm/-wal sidecars
    next to it. Only safe for a static backup file; a live database's WAL
    must stay visible, so a live source leaves this False.
    """
    uri = f"{path.resolve().as_uri()}?mode={mode}"
    if immutable:
        uri += "&immutable=1"
    return uri


def remove_sqlite_sidecars(db_path: Path) -> None:
    """Remove ``-journal``/``-wal``/``-shm`` sidecars next to ``db_path``.

    Keeps a published backup file self-contained instead of depending on
    sidecars that a later copy or move would leave behind.
    """
    for suffix in ("-journal", "-wal", "-shm"):
        db_path.with_name(f"{db_path.name}{suffix}").unlink(missing_ok=True)


def sqlite_backup_into(
    source_path: Path,
    dest_path: Path,
    *,
    source_mode: str = "ro",
    immutable: bool = False,
    reset_journal_mode: bool = False,
) -> None:
    """Copy ``source_path`` into ``dest_path`` via SQLite's online backup API.

    Opens ``source_path`` in ``source_mode`` (default read-only, never
    creating a missing file) so a writer's committed-but-uncheckpointed WAL
    pages are included, and connects to ``dest_path`` with a normal
    read-write connection so SQLite's own locking and journal mode govern
    the write.

    ``immutable`` opens the source as an immutable SQLite URI; only pass it
    for a static backup file (see ``sqlite_source_uri``), never for a live
    database source, or its WAL would be ignored and uncheckpointed rows
    lost.

    ``reset_journal_mode`` runs ``PRAGMA journal_mode=DELETE`` on ``dest``
    after the copy. The backup API copies page 1 verbatim, so a snapshot
    taken from a WAL-mode source would otherwise publish a WAL-flagged
    file; only set this when publishing a standalone snapshot, never when
    restoring into a live database whose own journal mode must be kept.
    """
    source_conn = sqlite3.connect(
        sqlite_source_uri(source_path, source_mode, immutable=immutable), uri=True
    )
    try:
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            source_conn.backup(dest_conn)
            if reset_journal_mode:
                dest_conn.execute("PRAGMA journal_mode=DELETE")
        finally:
            dest_conn.close()
    finally:
        source_conn.close()


def snapshot_sqlite_database(source_path: Path, dest_path: Path) -> None:
    """Snapshot ``source_path`` into the already-created ``dest_path``.

    Shared by regular SQLite backups and the pre-restore safety snapshot, so
    both go through SQLite's backup API and end up as self-contained files
    with no leftover -journal/-wal/-shm sidecars.
    """
    sqlite_backup_into(source_path, dest_path, reset_journal_mode=True)
    remove_sqlite_sidecars(dest_path)


def compute_checksum(path: Path) -> str:
    """Return the hex-encoded SHA-256 checksum of ``path``."""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksum_path(backup_path: Path) -> Path:
    """Return the sidecar checksum path for ``backup_path``."""
    return backup_path.with_name(f"{backup_path.name}{CHECKSUM_SUFFIX}")


def write_checksum(backup_path: Path) -> Path:
    """Record ``backup_path``'s SHA-256 checksum in a sidecar file."""
    digest = compute_checksum(backup_path)
    sidecar = checksum_path(backup_path)
    fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, BACKUP_FILE_MODE)
    with os.fdopen(fd, "w") as sidecar_file:
        sidecar_file.write(f"{digest}  {backup_path.name}\n")
    return sidecar


def verify_checksum(backup_path: Path) -> bool:
    """Verify ``backup_path`` against its recorded checksum, if any.

    Returns False when no sidecar checksum exists (e.g. a backup taken
    before this feature was added), so callers can warn instead of blocking
    a restore. Raises ChecksumError when a sidecar exists but no longer
    matches the backup file, since that indicates corruption or tampering
    rather than a missing older-format sidecar.
    """
    sidecar = checksum_path(backup_path)
    if not sidecar.exists():
        return False

    recorded = sidecar.read_text(encoding="utf-8").split()[0]
    actual = compute_checksum(backup_path)
    if actual != recorded:
        raise ChecksumError(
            f"Checksum mismatch for {backup_path.name}: expected {recorded}, got {actual}"
        )
    return True


def warn_if_checksum_missing(backup_file: Path) -> None:
    """Verify ``backup_file``'s checksum, warning instead of raising when none
    is recorded.

    Shared by every restore path (SQLite, PostgreSQL host, PostgreSQL
    Docker) so the missing-checksum warning is logged and printed in exactly
    one place. A recorded-but-mismatched checksum still raises ChecksumError
    from the underlying verify_checksum() call.
    """
    if not verify_checksum(backup_file):
        logger.warning(f"No checksum recorded for {backup_file.name}; skipping integrity check")
        print(f"Warning: no checksum recorded for {backup_file.name}; skipping integrity check")


def publish_backup(
    partial_path: Path,
    backup_path: Path,
    backup_dir: Path,
    glob_pattern: str,
    max_keep: int,
    name_pattern: Optional[re.Pattern[str]] = None,
    *,
    empty: bool,
    empty_message: str,
) -> None:
    """Finish a backup: reject an empty result, then publish, checksum and rotate.

    Shared by the SQLite and PostgreSQL (host and Docker) backup paths so the
    publish / checksum / rotate / print sequence lives in exactly one place.
    ``empty`` is precomputed by the caller: an uncompressed byte count for
    PostgreSQL (gzip's header keeps the compressed file non-zero even for an
    empty dump), or the raw file size for SQLite.
    """
    if empty:
        logger.error(empty_message)
        print(f"Error: {empty_message}")
        partial_path.unlink()
        raise BackupError(empty_message)

    logger.info(f"Backup file size: {format_size(partial_path.stat().st_size)}")
    partial_path.replace(backup_path)
    write_checksum(backup_path)

    removed = rotate_backups(backup_dir, glob_pattern, max_keep, name_pattern)
    if removed:
        logger.info(f"Removing {len(removed)} old backup(s) to maintain limit of {max_keep}")
        for old in removed:
            print(f"Removed old backup: {old.name}")
            logger.warning(f"Removed old backup: {old.name}")
    print(f"Backup created: {backup_path}")
    logger.info(f"Backup created successfully: {backup_path.name}")


def format_size(size_bytes: int) -> str:
    """Format byte count as ``<x.xx> MB``."""
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_backups(backup_dir: str | Path, db_type: str) -> list[Path]:
    """Return backup files matching ``db_type``, newest first."""
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return []

    if db_type == "sqlite":
        backups = list(backup_path.glob("*.sqlite3"))
    elif db_type == "postgres":
        backups = list(backup_path.glob("*.sql.gz"))
    else:
        logger.warning(f"Unknown db_type: {db_type}, showing all backups")
        backups = list(backup_path.glob("*"))

    backups.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return backups


def backup_name_pattern(stem: str, suffix: str) -> re.Pattern[str]:
    """Return an anchored pattern matching one database's backup file names.

    A plain glob such as ``f"{stem}_*{suffix}"`` also matches another
    database whose name has ``stem`` as a prefix (e.g. "repom" vs.
    "repom_dev", where the glob's ``*`` also swallows "dev_<timestamp>").
    Filtering candidates with ``pattern.fullmatch(name)`` keeps rotation and
    incomplete-file cleanup scoped to exactly this database's timestamped
    files.
    """
    return re.compile(re.escape(stem) + r"_\d{8}_\d{6}" + re.escape(suffix))


def parse_backup_source_database(name: str, suffix: str) -> Optional[str]:
    """Return the database name encoded in a backup file name, if any.

    Matches the ``<database>_<YYYYmmdd_HHMMSS><suffix>`` shape written by
    db_backup. Returns None when ``name`` doesn't match that shape, or for a
    legacy PostgreSQL backup named ``db_<YYYYmmdd_HHMMSS>.sql.gz`` (the fixed
    "db" prefix used before repom#157), whose source database is unknown.
    """
    match = re.fullmatch(r"(.+)_\d{8}_\d{6}" + re.escape(suffix), name)
    if not match:
        return None
    source = match.group(1)
    if suffix == ".sql.gz" and source == "db":
        return None
    return source


def cleanup_incomplete_backups(
    backup_dir: Path,
    glob_pattern: str,
    name_pattern: Optional[re.Pattern[str]] = None,
) -> list[Path]:
    """Remove zero-byte backup files and stale partial artifacts.

    When ``name_pattern`` is given, only files whose name fullmatches it are
    considered, so a ``glob_pattern`` that is also a prefix of another
    database's files (see ``backup_name_pattern``) doesn't reach them.
    """
    incomplete_files = []
    for path in backup_dir.glob(glob_pattern):
        if name_pattern is not None and not name_pattern.fullmatch(path.name):
            continue
        try:
            if path.stat().st_size == 0:
                path.unlink(missing_ok=True)
                checksum_path(path).unlink(missing_ok=True)
                incomplete_files.append(path)
        except FileNotFoundError:
            continue

    stale_partial_cutoff = time.time() - STALE_PARTIAL_BACKUP_AGE_SECONDS
    for path in backup_dir.glob(f"{glob_pattern}.partial"):
        if name_pattern is not None and not name_pattern.fullmatch(
            path.name.removesuffix(".partial")
        ):
            continue
        try:
            if path.stat().st_mtime <= stale_partial_cutoff:
                path.unlink(missing_ok=True)
                incomplete_files.append(path)
        except FileNotFoundError:
            continue

    return incomplete_files


def rotate_backups(
    backup_dir: Path,
    glob_pattern: str,
    max_keep: int,
    name_pattern: Optional[re.Pattern[str]] = None,
) -> list[Path]:
    """Remove incomplete and old backup files and return the removed paths.

    Rotation keeps the newest ``max_keep`` non-empty final files by modification
    time. A ``max_keep`` value of 0 or less disables retention deletion.
    ``name_pattern``, when given, scopes both incomplete-file cleanup and
    retention to files whose name fullmatches it (see
    ``cleanup_incomplete_backups`` and ``backup_name_pattern``).
    """
    removed_files = cleanup_incomplete_backups(backup_dir, glob_pattern, name_pattern)
    if max_keep <= 0:
        return removed_files

    files = []
    for path in backup_dir.glob(glob_pattern):
        if name_pattern is not None and not name_pattern.fullmatch(path.name):
            continue
        try:
            files.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            continue

    files.sort(key=lambda file: file[0])
    old_files = [path for _, path in files[:-max_keep]]
    for old_file in old_files:
        old_file.unlink(missing_ok=True)
        checksum_path(old_file).unlink(missing_ok=True)
    return removed_files + old_files


def build_host_pg_env(
    password: str | None,
    sslmode: str | None = None,
    sslrootcert: str | None = None,
) -> dict[str, str]:
    """Build the environment for a host libpq client tool (pg_dump/pg_restore/psql).

    Shared by pg_dump_tools._run_host_command and the db_backup / db_restore
    host paths so all three carry the same effective PGPASSWORD / PGSSLMODE /
    PGSSLROOTCERT instead of each copying os.environ separately. sslmode and
    sslrootcert are only set when provided, so a caller that has not resolved
    them (e.g. a directly constructed PgConnParams) leaves any inherited
    PGSSLMODE / PGSSLROOTCERT untouched.
    """
    env = os.environ.copy()
    if password is not None:
        env["PGPASSWORD"] = password
    if sslmode is not None:
        env["PGSSLMODE"] = sslmode
    if sslrootcert is not None:
        env["PGSSLROOTCERT"] = sslrootcert
    return env


def build_pg_client_command(
    tool: str,
    *,
    host: str,
    port: int,
    user: str,
    database: str,
    extra_args: Sequence[str] = (),
    container_name: str | None = None,
    stdin: bool = False,
) -> list[str]:
    """Build argv for a PostgreSQL client tool (pg_dump / psql / pg_restore).

    Shared by db_backup, db_restore and pg_dump_tools so host and Docker
    argv are built in exactly one place. Returns host argv (``<tool> -h host
    -p port -U user -d database ...``) when ``container_name`` is None, or
    Docker argv (``docker exec [-i] <container_name> <tool> -U user -d
    database ...``) otherwise. ``stdin=True`` adds Docker exec's ``-i`` flag
    so this process's stdin is forwarded into the container; host argv
    always carries stdin through subprocess.Popen directly, so ``stdin`` has
    no effect there.
    """
    if container_name is not None:
        command = ["docker", "exec"]
        if stdin:
            command.append("-i")
        command.append(container_name)
        command.extend([tool, "-U", user, "-d", database])
    else:
        command = [tool, "-h", host, "-p", str(port), "-U", user, "-d", database]
    command.extend(extra_args)
    return command


def mask_password(text: str, password: str | None) -> str:
    """Replace ``password`` with "***" in text destined for logs or errors."""
    if password:
        return text.replace(password, "***")
    return text


class ByteCountingWriter:
    """Wrap a binary writer, counting the bytes written through it.

    Lets a caller learn the uncompressed byte count streamed into a gzip
    writer without buffering it separately - publish_backup's empty check
    must not be fooled by gzip's header, which keeps the compressed file
    non-zero even for an empty dump.
    """

    def __init__(self, wrapped: BinaryIO) -> None:
        self._wrapped = wrapped
        self.bytes_written = 0

    def write(self, data: bytes) -> int:
        self.bytes_written += len(data)
        return self._wrapped.write(data)


@dataclass(frozen=True)
class StreamedCommandResult:
    """Exit status and masked stderr text from run_streaming_command."""

    returncode: int
    stderr: str


def _is_closed_stdin_pipe_error(exc: OSError) -> bool:
    """True for the write/close errors a child's early stdin exit raises.

    A child (psql/pg_restore) that stops reading stdin and exits makes the
    next write to its stdin pipe raise BrokenPipeError (errno EPIPE) on
    POSIX; on Windows the same condition can surface as a plain OSError with
    errno EINVAL instead.
    """
    return isinstance(exc, BrokenPipeError) or exc.errno in (errno.EPIPE, errno.EINVAL)


def run_streaming_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    stdin_file: BinaryIO | None = None,
    stdout_file: BinaryIO | None = None,
    password: str | None = None,
) -> StreamedCommandResult:
    """Run ``command``, streaming stdin/stdout through file objects.

    Shared by the host and Docker execution paths in db_backup, db_restore
    and pg_dump_tools, since a Docker argv (built by build_pg_client_command)
    is just another command to launch here. Exactly one of ``stdin_file``
    (copied into the child's stdin, e.g. a decompressing gzip reader) or
    ``stdout_file`` (filled from the child's stdout, e.g. a compressing gzip
    writer) is normally given, matching a dump (stdout) or restore (stdin)
    direction; neither side ever buffers a whole dump/restore payload in
    memory.

    stderr is drained on a background thread into a spooled temporary file
    while the main thread does the stdin/stdout copy, so a child writing
    more to stderr than an OS pipe buffer holds can never deadlock this call
    (see repom#167: pg_dump writing >64KB of stderr while nobody read it hung
    forever). The drained stderr is decoded and password-masked before being
    returned.

    A child that stops reading stdin and exits early (ON_ERROR_STOP failure,
    authentication failure, missing role) makes the stdin copy - or the
    subsequent close - raise BrokenPipeError/OSError instead of finishing.
    That is caught here so the child's real exit code and stderr are
    returned instead of the pipe error propagating and hiding them
    (repom#167). If the copy was cut short but the child still exited 0,
    that is reported as a failure (returncode 1) rather than success, since
    it means the child did not read all of its input.
    """
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if stdin_file is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE if stdout_file is not None else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
    )

    stderr_capture = tempfile.SpooledTemporaryFile(max_size=STREAMED_STDERR_SPOOL_LIMIT)
    stderr_thread = threading.Thread(
        target=shutil.copyfileobj, args=(process.stderr, stderr_capture), daemon=True
    )
    stderr_thread.start()

    stdin_cut_short = False
    try:
        if stdout_file is not None:
            shutil.copyfileobj(process.stdout, stdout_file)
        if stdin_file is not None:
            try:
                shutil.copyfileobj(stdin_file, process.stdin)
            except OSError as exc:
                if not _is_closed_stdin_pipe_error(exc):
                    raise
                stdin_cut_short = True
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError as exc:
                if not _is_closed_stdin_pipe_error(exc):
                    raise
                stdin_cut_short = True
        stderr_thread.join()
        process.stderr.close()
        process.wait()

    stderr_capture.seek(0)
    stderr_text = stderr_capture.read().decode("utf-8", errors="replace")
    stderr_capture.close()
    stderr_text = mask_password(stderr_text, password)

    returncode = process.returncode
    if stdin_cut_short and returncode == 0:
        note = "Command exited before reading all input"
        stderr_text = f"{stderr_text}\n{note}" if stderr_text else note
        returncode = 1

    return StreamedCommandResult(returncode=returncode, stderr=stderr_text)


def gzip_decompress_to_temp_file(source: Path) -> Path:
    """Fully decompress ``source`` into a new sibling 0600 temp file.

    Reads the entire gzip stream before returning, so a truncated or
    corrupt archive raises here (gzip.BadGzipFile / EOFError) before any of
    its content reaches a client tool's stdin - a restore must fail before
    the child process starts, not partway through applying it. The caller
    owns the returned path and must unlink it when done.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=source.parent, prefix=f"{source.name}.", suffix=".decompressed"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    os.chmod(tmp_path, BACKUP_FILE_MODE)
    try:
        with gzip.open(source, "rb") as compressed, open(tmp_path, "wb") as decompressed:
            shutil.copyfileobj(compressed, decompressed)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


def run_postgres_via_docker_or_host(
    *,
    via_docker: Callable[[], T],
    via_host: Callable[[], T],
    operation: str,
    host_tools: str = "host tools",
    container_name: str | None = None,
) -> T:
    """Run a PostgreSQL operation via Docker when available, otherwise host tools."""
    resolved_container_name = container_name or config.postgres.container.get_container_name()

    try:
        is_running = is_container_running(resolved_container_name)
    except DockerUnavailableError as exc:
        logger.warning(
            f"Docker unavailable while checking container {resolved_container_name} "
            f"({exc}); falling back to {host_tools} for PostgreSQL {operation}."
        )
        return via_host()

    if is_running:
        logger.info(f"Container {resolved_container_name} is running, using Docker exec")
        return via_docker()

    logger.warning(
        f"Container {resolved_container_name} is not running, falling back to {host_tools}. "
        f"Consider running 'uv run postgres_start' first."
    )
    return via_host()
