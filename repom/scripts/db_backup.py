from repom.config import config
from repom.logging import get_logger
import os
import shutil
from datetime import datetime

# ロガーを取得
logger = get_logger(__name__)

# Maximum number of backups to keep per database name
MAX_BACKUPS_PER_DB = 3


def main():
    logger.info("Starting database backup process")
    if config.db_type != "sqlite":
        logger.info("Database backup is only supported for SQLite; skipped")
        return
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database file: {config.sqlite.db_file_path}")

    # Ensure backup directory exists
    os.makedirs(config.db_backup_path, exist_ok=True)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Get original db file name and extension
    base_name = os.path.basename(config.sqlite.db_file_path)
    name, ext = os.path.splitext(base_name)
    # Format datetime (no milliseconds)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create backup file name: <name>_<datetime><ext>
    backup_name = f"{name}_{now_str}{ext}"
    backup_path = os.path.join(config.db_backup_path, backup_name)
    logger.debug(f"Backup file name: {backup_name}")

    # Find existing backups for this db name
    existing = [f for f in os.listdir(config.db_backup_path)
                if f.startswith(name + "_") and f.endswith(ext)]
    # Sort by creation time (oldest first)
    existing.sort()
    logger.debug(f"Found {len(existing)} existing backups for {name}")

    if len(existing) >= MAX_BACKUPS_PER_DB:
        # Remove oldest backups to keep only MAX_BACKUPS_PER_DB-1
        to_remove = existing[:len(existing) - MAX_BACKUPS_PER_DB + 1]
        logger.info(f"Removing {len(to_remove)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
        for old in to_remove:
            old_path = os.path.join(config.db_backup_path, old)
            os.remove(old_path)
            print(f"Removed old backup: {old}")
            logger.warning(f"Removed old backup: {old}")

    # Copy the file
    logger.debug(f"Copying {config.sqlite.db_file_path} to {backup_path}")
    shutil.copy2(config.sqlite.db_file_path, backup_path)
    print(f"Backup created: {backup_path}")
    logger.info(f"Backup created successfully: {backup_name}")
    logger.info("Database backup process completed")


if __name__ == "__main__":
    main()
