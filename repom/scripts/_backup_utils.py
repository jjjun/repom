from pathlib import Path


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
