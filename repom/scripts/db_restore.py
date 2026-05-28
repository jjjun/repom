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
import os
import shutil
import subprocess
import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional

from repom.scripts._backup_utils import (
    format_size,
    get_backups,
    run_postgres_via_docker_or_host,
)

logger = get_logger(__name__)


def display_backups(backups: list[Path]) -> Optional[Path]:
    """Display the list of backups and let the user select one.

    Args:
        backups: list of backup files

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
        print(f"[{i}] {backup.name} ({size}) - {modified_str}{latest_mark}")

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

    current_db = Path(config.sqlite.db_file_path)

    # If the current DB exists, create an automatic backup of it first
    if current_db.exists():
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        auto_backup_name = f"restore_backup_{now_str}.sqlite3"
        auto_backup_path = Path(config.db_backup_path) / auto_backup_name

        logger.info(f"Creating automatic backup of current database: {auto_backup_name}")
        print(f"Creating backup of current database: {auto_backup_name}")
        shutil.copy2(current_db, auto_backup_path)
        logger.debug(f"Backup saved to {auto_backup_path}")

    # Overwrite the current DB with the backup file
    try:
        logger.info(f"Restoring {backup_file.name} to {current_db}")
        shutil.copy2(backup_file, current_db)
        print("\nRestore completed successfully")
        print(f"  Database: {current_db}")
        logger.info("SQLite restore completed successfully")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\nRestore failed: {e}")
        raise


def restore_postgresql_via_host(backup_file: Path):
    """Restore a PostgreSQL database using host gunzip/psql.

    Used as a fallback when no Docker container is running. Requires gunzip
    and psql to be installed in the host environment.

    Args:
        backup_file: source backup file to restore from (.sql.gz)
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    try:
        # Set PGPASSWORD in the environment
        env = os.environ.copy()
        env['PGPASSWORD'] = config.postgres.password

        # Restore with gunzip + psql
        logger.debug("Decompressing backup file")

        # Decompress the backup with gunzip and pipe it to psql
        gunzip_proc = subprocess.Popen(
            ['gunzip', '-c', str(backup_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Restore with the psql command
        psql_cmd = [
            'psql',
            '-h', config.postgres.host,
            '-p', str(config.postgres.port),
            '-U', config.postgres.user,
            '-d', config.postgres_db,
            '-v', 'ON_ERROR_STOP=1',  # stop on error
        ]

        logger.debug(f"Executing: {' '.join(psql_cmd)} (PGPASSWORD hidden)")
        print("Restoring database...")

        psql_proc = subprocess.Popen(
            psql_cmd,
            stdin=gunzip_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # Close gunzip's stdout so psql can consume it
        gunzip_proc.stdout.close()

        # Wait for the processes to finish
        psql_stdout, psql_stderr = psql_proc.communicate()
        gunzip_stderr = gunzip_proc.stderr.read()

        # Check gunzip errors
        if gunzip_proc.returncode != 0:
            error_msg = gunzip_stderr.decode('utf-8')
            logger.error(f"gunzip failed: {error_msg}")
            print(f"\nError: Failed to decompress backup file\n{error_msg}")
            return

        # Check psql errors
        if psql_proc.returncode != 0:
            error_msg = psql_stderr.decode('utf-8')
            logger.error(f"psql restore failed: {error_msg}")
            print(f"\nError: Restore failed\n{error_msg}")
            return

        print("\nRestore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError as e:
        if 'gunzip' in str(e):
            logger.error("gunzip command not found")
            print("\nError: gunzip command not found")
            print("Please install gzip utilities")
        elif 'psql' in str(e):
            logger.error("psql command not found")
            print("\nError: psql command not found")
            print("Please install PostgreSQL client tools and ensure 'psql' is in your PATH")
        else:
            logger.error(f"Command not found: {e}")
            print(f"\nError: Required command not found: {e}")
        return
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\nError: Restore failed: {e}")
        raise


def restore_postgresql_via_docker(backup_file: Path):
    """Restore a PostgreSQL database using docker exec.

    Runs psql inside the Docker container to perform the restore. No host
    PostgreSQL client tools installation is required.

    Args:
        backup_file: source backup file to restore from (.sql.gz)
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    container_name = config.postgres.container.get_container_name()
    logger.info(f"Using Docker container: {container_name}")

    try:
        # Decompress the backup file
        logger.debug("Decompressing backup file")
        with gzip.open(backup_file, 'rb') as gz_file:
            sql_data = gz_file.read()

        logger.debug(f"Backup file decompressed: {len(sql_data)} bytes")

        # Build the psql command
        psql_cmd = [
            "psql",
            "-U", config.postgres.user,
            "-d", config.postgres_db,
            "-v", "ON_ERROR_STOP=1",  # stop on error
        ]

        logger.debug(f"Executing: docker exec -i {container_name} {' '.join(psql_cmd)}")
        print("Restoring database...")

        # Run psql via docker exec -i (feed SQL from stdin)
        DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=psql_cmd,
            stdin=sql_data,
            capture_output=True
        )

        print("\nRestore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError:
        logger.error("docker command not found. Please install Docker Desktop.")
        print("\nError: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        return
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"psql restore failed: {error_msg}")
        print(f"\nError: Restore failed\n{error_msg}")
        return
    except gzip.BadGzipFile:
        logger.error("Invalid gzip file")
        print("\nError: Invalid backup file (not a gzip file)")
        return
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\nError: Restore failed: {e}")
        raise


def restore_postgresql(backup_file: Path):
    """Entry point for PostgreSQL restore.

    Uses docker exec when the Docker container is running, and falls back to
    host gunzip/psql when it is stopped.

    Args:
        backup_file: source backup file to restore from (.sql.gz)
    """
    run_postgres_via_docker_or_host(
        via_docker=lambda: restore_postgresql_via_docker(backup_file),
        via_host=lambda: restore_postgresql_via_host(backup_file),
        operation="restore",
    )


def main():
    logger.info("Starting database restore process")

    # Check that the backup directory exists
    if not os.path.exists(config.db_backup_path):
        print(f"Error: Backup directory not found: {config.db_backup_path}")
        logger.error(f"Backup directory not found: {config.db_backup_path}")
        return

    # Get the backup files
    backups = get_backups(config.db_backup_path, config.db_type)

    if not backups:
        print(f"No backups found in {config.db_backup_path}")
        logger.info("No backups found")
        return

    # Let the user select a backup
    selected = display_backups(backups)

    if not selected:
        logger.info("Restore cancelled by user")
        return

    # Confirmation message
    print(f"\nSelected: {selected.name}")
    confirm = input(f"Confirm restore from {selected.name}? [y/N]: ").strip().lower()

    if confirm != 'y':
        print("Restore cancelled")
        logger.info("Restore cancelled by user")
        return

    # Determine db_type from the file extension
    is_sqlite = selected.suffix == '.sqlite3'
    is_postgres = selected.name.endswith('.sql.gz')

    # Run the restore
    try:
        if is_sqlite and config.db_type == 'sqlite':
            restore_sqlite(selected)
        elif is_postgres and config.db_type == 'postgres':
            restore_postgresql(selected)
        else:
            print("\nError: Backup file type mismatch")
            print(f"  Current db_type: {config.db_type}")
            print(f"  Backup file: {selected.name}")
            logger.error(f"Backup file type mismatch: {config.db_type} vs {selected.name}")
            return

    except Exception as e:
        logger.error(f"Restore process failed: {e}")
        print("\nRestore process failed")
        return

    logger.info("Database restore process completed")


if __name__ == "__main__":
    main()
