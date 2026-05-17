from tests._init import *

from repom.scripts._backup_utils import rotate_backups


def _touch(path, mtime):
    path.write_text(path.name, encoding="utf-8")
    path.touch()
    import os
    os.utime(path, (mtime, mtime))


def test_rotate_backups_keeps_newest_by_mtime(tmp_path):
    old = tmp_path / "db_20260101_000000.sql.gz"
    middle = tmp_path / "db_20260102_000000.sql.gz"
    new = tmp_path / "db_20260103_000000.sql.gz"
    _touch(old, 1)
    _touch(middle, 2)
    _touch(new, 3)

    removed = rotate_backups(tmp_path, "db_*.sql.gz", max_keep=2)

    assert removed == [old]
    assert not old.exists()
    assert middle.exists()
    assert new.exists()


def test_rotate_backups_keeps_single_newest(tmp_path):
    first = tmp_path / "app_1.sqlite3"
    second = tmp_path / "app_2.sqlite3"
    _touch(first, 1)
    _touch(second, 2)

    removed = rotate_backups(tmp_path, "app_*.sqlite3", max_keep=1)

    assert removed == [first]
    assert not first.exists()
    assert second.exists()


def test_rotate_backups_does_not_delete_when_limit_is_zero(tmp_path):
    first = tmp_path / "app_1.sqlite3"
    second = tmp_path / "app_2.sqlite3"
    _touch(first, 1)
    _touch(second, 2)

    removed = rotate_backups(tmp_path, "app_*.sqlite3", max_keep=0)

    assert removed == []
    assert first.exists()
    assert second.exists()


def test_rotate_backups_ignores_non_matching_files(tmp_path):
    matching = tmp_path / "db_1.sql.gz"
    ignored = tmp_path / "notes.txt"
    _touch(matching, 1)
    _touch(ignored, 2)

    removed = rotate_backups(tmp_path, "db_*.sql.gz", max_keep=1)

    assert removed == []
    assert matching.exists()
    assert ignored.exists()
