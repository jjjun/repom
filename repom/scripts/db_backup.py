from repom.config import config
import os
import shutil
from datetime import datetime

# Maximum number of backups to keep per database name
MAX_BACKUPS_PER_DB = 3


def main():
    # Ensure backup directory exists
    os.makedirs(config.db_backup_path, exist_ok=True)

    # Get original db file name and extension
    base_name = os.path.basename(config.db_file)
    name, ext = os.path.splitext(base_name)
    # Format datetime (no milliseconds)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create backup file name: <name>_<datetime><ext>
    backup_name = f"{name}_{now_str}{ext}"
    backup_path = os.path.join(config.db_backup_path, backup_name)

    # Find existing backups for this db name
    existing = [f for f in os.listdir(config.db_backup_path)
                if f.startswith(name + "_") and f.endswith(ext)]
    # Sort by creation time (oldest first)
    existing.sort()
    if len(existing) >= MAX_BACKUPS_PER_DB:
        # Remove oldest backups to keep only MAX_BACKUPS_PER_DB-1
        to_remove = existing[:len(existing) - MAX_BACKUPS_PER_DB + 1]
        for old in to_remove:
            os.remove(os.path.join(config.db_backup_path, old))
            print(f"Removed old backup: {old}")

    # Copy the file
    shutil.copy2(config.db_file_path, backup_path)
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
