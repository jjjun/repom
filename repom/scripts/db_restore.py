"""Database restore script.

Selects a backup file from the backup directory interactively and restores
the database.

Usage:
    uv run db_restore

    # Specify environment
    EXEC_ENV=dev uv run db_restore
"""

from repom.config import config
from repom.logging import get_logger
from basekit.docker_manager import DockerCommandExecutor
import gzip
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from repom.scripts._backup_utils import (
    RestoreError,
    build_host_pg_env,
    build_pg_client_command,
    format_size,
    get_backups,
    gzip_decompress_to_temp_file,
    open_backup_temp_file,
    parse_backup_source_database,
    run_postgres_via_docker_or_host,
    run_streaming_command,
    snapshot_sqlite_database,
    sqlite_backup_into,
    warn_if_checksum_missing,
    write_checksum,
)

logger = get_logger(__name__)


def display_backups(backups: list[Path], target: str, suffix: str) -> Optional[Path]:
    """Display the list of backups and let the user select one.

    Args:
        backups: list of backup files, current database's backups first
        target: name of the database a restore would write into
        suffix: backup file suffix for the current db_type (".sql.gz" or
            ".sqlite3"), used to parse each backup's source database

    Returns:
        the selected backup file, or None when cancelled
    """
    if not backups:
        print("No backups found")
        return None

    print("\nAvailable backups:")
    print("=" * 60)

    for i, backup in enumerate(backups, 1):
        size = format_size(backup.stat().st_size)
        modified = datetime.fromtimestamp(backup.stat().st_mtime)
        modified_str = modified.strftime("%Y-%m-%d %H:%M:%S")
        latest_mark = " <- latest" if i == 1 else ""
        source = parse_backup_source_database(backup.name, suffix)
        if source is None:
            source_mark = " [legacy/unknown source database]"
        elif source != target:
            source_mark = f" [other database: {source}]"
        else:
            source_mark = ""
        print(f"[{i}] {backup.name} ({size}) - {modified_str}{latest_mark}{source_mark}")

    print("=" * 60)

    while True:
        user_input = input("\nSelect backup number to restore (or 'q' to cancel): ").strip()

        if user_input.lower() == 'q':
            print("Restore cancelled")
            return None

        try:
            index = int(user_input) - 1
            if 0 <= index < len(backups):
                return backups[index]
            else:
                print(f"Invalid number. Please enter 1-{len(backups)}")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'")


def restore_sqlite(backup_file: Path):
    """Restore a SQLite database.

    Args:
        backup_file: source backup file to restore from
    """
    logger.info(f"Starting SQLite restore from {backup_file.name}")

    try:
        warn_if_checksum_missing(backup_file)

        current_db = Path(config.sqlite.db_file_path)

        # If the current DB exists, create an automatic backup of it first. This
        # goes through the same snapshot -> partial -> replace -> checksum path
        # as a regular backup (see db_backup.backup_sqlite), kept outside the
        # regular rotation glob so a restore never rotates away good backups.
        if current_db.exists():
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_backup_name = f"restore_backup_{now_str}.sqlite3"
            auto_backup_path = Path(config.db_backup_path) / auto_backup_name
            auto_partial_path = auto_backup_path.with_name(f"{auto_backup_path.name}.partial")

            logger.info(f"Creating automatic backup of current database: {auto_backup_name}")
            print(f"Creating backup of current database: {auto_backup_name}")
            open_backup_temp_file(auto_partial_path).close()
            try:
                snapshot_sqlite_database(current_db, auto_partial_path)
            except Exception:
                auto_partial_path.unlink(missing_ok=True)
                raise
            auto_partial_path.replace(auto_backup_path)
            write_checksum(auto_backup_path)
            logger.debug(f"Backup saved to {auto_backup_path}")

        # Overwrite the current DB with the backup file through SQLite's backup
        # API instead of replacing the live file, so the restore goes through
        # SQLite's own locking, keeps the destination journal mode, and other
        # connections see the restored content on their next read transaction.
        # immutable=True: the backup file is static, so this reads a WAL-flagged
        # legacy backup without SQLite creating -shm/-wal files next to it.
        logger.info(f"Restoring {backup_file.name} to {current_db}")
        sqlite_backup_into(backup_file, current_db, immutable=True)
        print("\nRestore completed successfully")
        print(f"  Database: {current_db}")
        logger.info("SQLite restore completed successfully")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\nRestore failed: {e}")
        raise RestoreError(f"Restore failed: {e}") from e


def _psql_command(container_name: str | None) -> list[str]:
    """Build the psql argv for the host or Docker path.

    A separate function so tests can substitute a stand-in child process
    while still exercising the real streaming path in _restore_postgresql.
    """
    return build_pg_client_command(
        "psql",
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        database=config.postgres_db,
        extra_args=["-v", "ON_ERROR_STOP=1"],  # stop on error
        container_name=container_name,
        stdin=True,
    )


def _restore_postgresql(backup_file: Path, container_name: str | None) -> None:
    """PostgreSQL データベースのリストア処理（ホスト / Docker exec 共通）

    gzip.open(backup_file) のストリームを直接 psql の stdin へ流し込み、
    外部 gunzip コマンドには依存しない。psql を起動する前にアーカイブ全体を
    一時ファイルへ展開して検証するため、破損／切り詰められた gzip は
    プロセスを起動する前に失敗する。stderr は別スレッドでドレインして
    デッドロックを防ぐ（repom#167）。
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    env = None
    if container_name is None:
        # sslmode / sslrootcert を解決・検証する（db_url と同じロジックを共有）。
        # subprocess を起動する前に検証することで、prod での弱い sslmode を
        # プロセス起動前に拒否する。
        tls = config.postgres_tls_settings()
        env = build_host_pg_env(config.postgres.password, tls.sslmode, tls.sslrootcert)

    try:
        warn_if_checksum_missing(backup_file)

        # 破損／切り詰められた gzip はここで検出し、psql を起動する前に失敗させる
        logger.debug("Decompressing backup file")
        sql_path = gzip_decompress_to_temp_file(backup_file)
        try:
            command = _psql_command(container_name)
            logger.debug(f"Executing: {' '.join(command)} (PGPASSWORD hidden)")
            print("Restoring database...")

            with open(sql_path, "rb") as sql_file:
                result = run_streaming_command(
                    command, env=env, stdin_file=sql_file, password=config.postgres.password
                )
        finally:
            sql_path.unlink(missing_ok=True)

        if result.returncode != 0:
            logger.error(f"psql restore failed: {result.stderr}")
            print(f"\nError: Restore failed\n{result.stderr}")
            raise RestoreError(f"psql failed with exit code {result.returncode}: {result.stderr}")

        print("\nRestore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError as e:
        if container_name is None:
            logger.error("psql command not found")
            print("\nError: psql command not found")
            print("Please install PostgreSQL client tools and ensure 'psql' is in your PATH")
            raise RestoreError("psql command not found") from e
        logger.error("docker command not found. Please install Docker Desktop.")
        print("\nError: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        raise RestoreError("docker command not found") from e
    except RestoreError:
        # psql exited non-zero; already logged and printed above.
        raise
    except gzip.BadGzipFile as e:
        logger.error("Invalid gzip file")
        print("\nError: Invalid backup file (not a gzip file)")
        raise RestoreError("Invalid backup file (not a gzip file)") from e
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\nError: Restore failed: {e}")
        raise RestoreError(f"Restore failed: {e}") from e


def restore_postgresql_via_host(backup_file: Path):
    """Restore a PostgreSQL database by streaming a gzip backup into host psql.

    Used as a fallback when no Docker container is running. Requires psql to
    be installed in the host environment.

    Args:
        backup_file: source backup file to restore from (.sql.gz)
    """
    _restore_postgresql(backup_file, container_name=None)


def restore_postgresql_via_docker(backup_file: Path):
    """Restore a PostgreSQL database by streaming a gzip backup into psql via docker exec.

    No host PostgreSQL client tools installation is required.

    Args:
        backup_file: source backup file to restore from (.sql.gz)
    """
    container_name = config.postgres.container.get_container_name()
    logger.info(f"Using Docker container: {container_name}")
    _restore_postgresql(backup_file, container_name=container_name)


def restore_postgresql(backup_file: Path):
    """Entry point for PostgreSQL restore.

    Uses docker exec when the Docker container is running, and falls back to
    host psql when it is stopped.

    Args:
        backup_file: source backup file to restore from (.sql.gz)
    """
    run_postgres_via_docker_or_host(
        via_docker=lambda: restore_postgresql_via_docker(backup_file),
        via_host=lambda: restore_postgresql_via_host(backup_file),
        operation="restore",
    )


def target_database_name() -> str:
    """Return the name of the database a restore would write into."""
    if config.db_type == "postgres":
        return config.postgres_db
    return Path(config.sqlite.db_file_path).stem


def main():
    logger.info("Starting database restore process")

    # Check that the backup directory exists
    if not os.path.exists(config.db_backup_path):
        print(f"Error: Backup directory not found: {config.db_backup_path}")
        logger.error(f"Backup directory not found: {config.db_backup_path}")
        raise RestoreError(f"Backup directory not found: {config.db_backup_path}")

    # Get the backup files
    backups = get_backups(config.db_backup_path, config.db_type)

    if not backups:
        print(f"No backups found in {config.db_backup_path}")
        logger.info("No backups found")
        raise RestoreError(f"No backups found in {config.db_backup_path}")

    # List the target database's own backups first, then backups from other
    # (or unknown/legacy) source databases.
    target = target_database_name()
    suffix = ".sql.gz" if config.db_type == "postgres" else ".sqlite3"
    current_db_backups = [
        backup for backup in backups
        if parse_backup_source_database(backup.name, suffix) == target
    ]
    other_backups = [backup for backup in backups if backup not in current_db_backups]

    # Let the user select a backup
    selected = display_backups(current_db_backups + other_backups, target, suffix)

    if not selected:
        logger.info("Restore cancelled by user")
        return

    # Confirmation message: show the parsed source database alongside the
    # restore target, and require typing the target name (instead of "y")
    # whenever the backup's source is unknown or does not match, so a
    # cross-database restore can't happen with a single keystroke.
    source = parse_backup_source_database(selected.name, suffix)
    print(f"\nSelected: {selected.name}")
    print(f"  Source database: {source if source is not None else 'unknown (legacy backup)'}")
    print(f"  Target database: {target}")

    if source == target:
        confirm = input(f"Confirm restore from {selected.name}? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Restore cancelled")
            logger.info("Restore cancelled by user")
            return
    else:
        print(
            f"WARNING: this backup's source database ({source if source is not None else 'unknown'}) "
            f"does not match the target database ({target})."
        )
        confirm = input(
            f"Type the target database name ({target}) to confirm this cross-database "
            "restore, or anything else to cancel: "
        ).strip()
        if confirm != target:
            print("Restore cancelled")
            logger.info("Restore cancelled by user")
            return

    # Determine db_type from the file extension
    is_sqlite = selected.suffix == '.sqlite3'
    is_postgres = selected.name.endswith('.sql.gz')

    # Run the restore
    if is_sqlite and config.db_type == 'sqlite':
        restore_sqlite(selected)
    elif is_postgres and config.db_type == 'postgres':
        restore_postgresql(selected)

    logger.info("Database restore process completed")


if __name__ == "__main__":
    main()
