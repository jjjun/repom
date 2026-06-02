from tests._init import *

from unittest.mock import MagicMock

from repom.scripts import _backup_utils
from repom.scripts._backup_utils import (
    format_size,
    get_backups,
    rotate_backups,
    run_postgres_via_docker_or_host,
)


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


def test_format_size_formats_fixed_mb_values():
    assert format_size(0) == "0.00 MB"
    assert format_size(512) == "0.00 MB"
    assert format_size(1024 * 1024) == "1.00 MB"
    assert format_size(2.5 * 1024 * 1024) == "2.50 MB"


def test_get_backups_returns_sqlite_backups_newest_first(tmp_path):
    old = tmp_path / "app_20260101_000000.sqlite3"
    new = tmp_path / "app_20260102_000000.sqlite3"
    ignored = tmp_path / "db_20260102_000000.sql.gz"
    _touch(old, 1)
    _touch(new, 2)
    _touch(ignored, 3)

    assert get_backups(tmp_path, "sqlite") == [new, old]


def test_get_backups_returns_postgres_backups_newest_first(tmp_path):
    old = tmp_path / "db_20260101_000000.sql.gz"
    new = tmp_path / "db_20260102_000000.sql.gz"
    ignored = tmp_path / "app_20260102_000000.sqlite3"
    _touch(old, 1)
    _touch(new, 2)
    _touch(ignored, 3)

    assert get_backups(tmp_path, "postgres") == [new, old]


def test_get_backups_returns_empty_for_missing_directory(tmp_path):
    assert get_backups(tmp_path / "missing", "sqlite") == []


def test_run_postgres_via_docker_or_host_uses_docker_when_container_running(monkeypatch):
    via_docker = MagicMock(return_value="docker-result")
    via_host = MagicMock()

    monkeypatch.setattr(
        _backup_utils.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=True),
    )

    result = run_postgres_via_docker_or_host(
        via_docker=via_docker,
        via_host=via_host,
        operation="backup",
    )

    assert result == "docker-result"
    via_docker.assert_called_once_with()
    via_host.assert_not_called()


def test_run_postgres_via_docker_or_host_uses_host_when_container_stopped(monkeypatch):
    via_docker = MagicMock()
    via_host = MagicMock(return_value="host-result")

    monkeypatch.setattr(
        _backup_utils.DockerCommandExecutor,
        "is_container_running",
        MagicMock(return_value=False),
    )

    result = run_postgres_via_docker_or_host(
        via_docker=via_docker,
        via_host=via_host,
        operation="restore",
    )

    assert result == "host-result"
    via_docker.assert_not_called()
    via_host.assert_called_once_with()


def test_run_postgres_via_docker_or_host_uses_host_when_docker_missing(monkeypatch):
    via_docker = MagicMock()
    via_host = MagicMock(return_value="host-result")

    monkeypatch.setattr(
        _backup_utils.DockerCommandExecutor,
        "is_container_running",
        MagicMock(side_effect=FileNotFoundError("docker not found")),
    )

    result = run_postgres_via_docker_or_host(
        via_docker=via_docker,
        via_host=via_host,
        operation="backup",
    )

    assert result == "host-result"
    via_docker.assert_not_called()
    via_host.assert_called_once_with()


def test_run_postgres_via_docker_or_host_accepts_explicit_container_name(monkeypatch):
    is_running = MagicMock(return_value=True)
    monkeypatch.setattr(
        _backup_utils.DockerCommandExecutor,
        "is_container_running",
        is_running,
    )

    result = run_postgres_via_docker_or_host(
        via_docker=lambda: "docker-result",
        via_host=lambda: "host-result",
        operation="backup",
        container_name="custom-postgres",
    )

    assert result == "docker-result"
    is_running.assert_called_once_with("custom-postgres")
