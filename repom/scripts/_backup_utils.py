from pathlib import Path
import hashlib
import os
import re
import sqlite3
import time
from typing import BinaryIO, Callable, Optional, TypeVar

from repom.config import config
from repom.docker_service import DockerUnavailableError, is_container_running
from repom.logging import get_logger

logger = get_logger(__name__)
T = TypeVar("T")
STALE_PARTIAL_BACKUP_AGE_SECONDS = 24 * 60 * 60

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
