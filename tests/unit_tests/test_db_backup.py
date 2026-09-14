from tests._init import *

import os
from unittest.mock import MagicMock

import pytest

from repom.scripts import db_backup
from repom.scripts._backup_utils import checksum_path

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX file mode bits only")


class _FakePgDumpProc:
    """Stand-in for subprocess.Popen covering the pg_dump pipeline."""

    def __init__(self, returncode=0, stdout_lines=(b"SELECT 1;\n",), stderr=b""):
        self.returncode = returncode
        self.stdout = iter(stdout_lines)
        self._stderr = stderr

    def communicate(self):
        return b"", self._stderr


def _mock_postgres_config(backup_dir):
    config = MagicMock()
    config.db_backup_path = str(backup_dir)
    config.postgres.host = "localhost"
    config.postgres.port = 5432
    config.postgres.user = "postgres"
    config.postgres.password = "test-password"
    config.postgres_db = "repom_test"
    return config


def test_backup_postgresql_via_host_publishes_backup_and_checksum(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(db_backup.subprocess, "Popen", lambda *a, **k: _FakePgDumpProc())

    db_backup.backup_postgresql_via_host()

    backups = list(tmp_path.glob("db_*.sql.gz"))
    assert len(backups) == 1
    assert checksum_path(backups[0]).exists()
    assert list(tmp_path.glob("*.partial")) == []


@POSIX_ONLY
def test_backup_directory_is_0700(monkeypatch, tmp_path):
    backup_dir = tmp_path / "backups"
    config = _mock_postgres_config(backup_dir)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(db_backup.subprocess, "Popen", lambda *a, **k: _FakePgDumpProc())

    db_backup.backup_postgresql_via_host()

    assert backup_dir.stat().st_mode & 0o777 == 0o700


@POSIX_ONLY
def test_backup_file_is_0600(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(db_backup.subprocess, "Popen", lambda *a, **k: _FakePgDumpProc())

    db_backup.backup_postgresql_via_host()

    backups = list(tmp_path.glob("db_*.sql.gz"))
    assert len(backups) == 1
    assert backups[0].stat().st_mode & 0o777 == 0o600


@POSIX_ONLY
def test_backup_temp_file_never_world_readable(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)

    observed_modes = []

    def _stdout_lines():
        partial_files = list(tmp_path.glob("*.partial"))
        assert len(partial_files) == 1
        observed_modes.append(partial_files[0].stat().st_mode & 0o777)
        yield b"SELECT 1;\n"

    class _Proc:
        returncode = 0
        stdout = _stdout_lines()

        def communicate(self):
            return b"", b""

    monkeypatch.setattr(db_backup.subprocess, "Popen", lambda *a, **k: _Proc())

    db_backup.backup_postgresql_via_host()

    # Asserted while the file only existed as the .partial temp file, i.e.
    # at creation time rather than only after the atomic rename.
    assert observed_modes == [0o600]


def test_backup_raises_when_pg_dump_fails(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(
        db_backup.subprocess,
        "Popen",
        lambda *a, **k: _FakePgDumpProc(returncode=1, stderr=b"pg_dump: connection failed"),
    )

    with pytest.raises(RuntimeError, match="pg_dump"):
        db_backup.backup_postgresql_via_host()

    assert list(tmp_path.glob("db_*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []
