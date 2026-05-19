from pathlib import Path
from typing import Callable

from basekit.docker_manager import DockerCommandExecutor

from repom.config import config
from repom.logging import get_logger

logger = get_logger(__name__)


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
        backups = list(backup_path.glob("db_*.sql.gz"))
    else:
        logger.warning(f"Unknown db_type: {db_type}, showing all backups")
        backups = list(backup_path.glob("*"))

    backups.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return backups


def rotate_backups(backup_dir: Path, glob_pattern: str, max_keep: int) -> list[Path]:
    """Remove old backup files and return the removed paths.

    Rotation keeps the newest ``max_keep`` files by modification time. A
    ``max_keep`` value of 0 or less disables deletion.
    """
    if max_keep <= 0:
        return []

    files = sorted(backup_dir.glob(glob_pattern), key=lambda path: path.stat().st_mtime)
    old_files = files[:-max_keep]
    for old_file in old_files:
        old_file.unlink()
    return old_files


def run_postgres_via_docker_or_host(
    *,
    via_docker: Callable[[], None],
    via_host: Callable[[], None],
    operation: str,
    host_tools: str = "host tools",
) -> None:
    """Run a PostgreSQL operation via Docker when available, otherwise host tools."""
    container_name = config.postgres.container.get_container_name()

    try:
        is_running = DockerCommandExecutor.is_container_running(container_name)
    except FileNotFoundError:
        logger.warning(
            f"docker command not found while checking container {container_name}; "
            f"falling back to {host_tools} for PostgreSQL {operation}."
        )
        via_host()
        return

    if is_running:
        logger.info(f"Container {container_name} is running, using Docker exec")
        via_docker()
    else:
        logger.warning(
            f"Container {container_name} is not running, falling back to {host_tools}. "
            f"Consider running 'uv run postgres_start' first."
        )
        via_host()
