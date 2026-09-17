from tests._init import *

import os
import sqlite3
from unittest.mock import MagicMock

import pytest

from repom.config import PostgresTlsSettings
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


def _mock_postgres_config(backup_dir, sslmode="prefer", sslrootcert=None):
    config = MagicMock()
    config.db_backup_path = str(backup_dir)
    config.postgres.host = "localhost"
    config.postgres.port = 5432
    config.postgres.user = "postgres"
    config.postgres.password = "test-password"
    config.postgres_db = "repom_test"
    config.postgres_tls_settings.return_value = PostgresTlsSettings(
        sslmode=sslmode, sslrootcert=sslrootcert
    )
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


def test_backup_postgresql_via_host_passes_tls_settings_in_env(monkeypatch, tmp_path):
    config = _mock_postgres_config(
        tmp_path, sslmode="verify-full", sslrootcert="/etc/ssl/certs/test-ca.pem"
    )
    monkeypatch.setattr(db_backup, "config", config)
    popen_calls = []

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return _FakePgDumpProc()

    monkeypatch.setattr(db_backup.subprocess, "Popen", fake_popen)

    db_backup.backup_postgresql_via_host()

    env = popen_calls[-1][1]["env"]
    assert env["PGPASSWORD"] == "test-password"
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/etc/ssl/certs/test-ca.pem"


def test_backup_postgresql_via_host_overrides_inherited_sslmode(monkeypatch, tmp_path):
    monkeypatch.setenv("PGSSLMODE", "disable")
    config = _mock_postgres_config(tmp_path, sslmode="require")
    monkeypatch.setattr(db_backup, "config", config)
    popen_calls = []

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return _FakePgDumpProc()

    monkeypatch.setattr(db_backup.subprocess, "Popen", fake_popen)

    db_backup.backup_postgresql_via_host()

    assert popen_calls[-1][1]["env"]["PGSSLMODE"] == "require"


def test_backup_postgresql_via_host_raises_before_launching_process_on_invalid_tls(
    monkeypatch, tmp_path
):
    config = _mock_postgres_config(tmp_path)
    config.postgres_tls_settings.side_effect = ValueError(
        "PostgreSQL sslmode 'prefer' is not allowed in prod for a non-local host "
        "('db.example.com')"
    )
    monkeypatch.setattr(db_backup, "config", config)
    popen_calls = []
    monkeypatch.setattr(
        db_backup.subprocess,
        "Popen",
        lambda *a, **k: popen_calls.append((a, k)) or _FakePgDumpProc(),
    )

    with pytest.raises(ValueError, match="sslmode") as exc_info:
        db_backup.backup_postgresql_via_host()

    assert popen_calls == []
    assert list(tmp_path.glob("db_*.sql.gz")) == []
    assert "test-password" not in str(exc_info.value)


def _mock_sqlite_config(backup_dir, db_file_path):
    config = MagicMock()
    config.db_backup_path = str(backup_dir)
    config.sqlite.db_file_path = str(db_file_path)
    return config


def _make_wal_db_with_uncheckpointed_row(db_path, row_id=42):
    """Create a WAL-mode SQLite db with a committed row still sitting in the WAL.

    Mirrors the repom#145 repro: wal_autocheckpoint=0, a checkpoint taken
    before the row is inserted, and the writer connection left open.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE items (id INTEGER)")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("INSERT INTO items VALUES (?)", (row_id,))
    conn.commit()
    return conn


def test_backup_sqlite_includes_uncheckpointed_wal_data(monkeypatch, tmp_path):
    db_file = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(db_file)
    try:
        backup_dir = tmp_path / "backups"
        config = _mock_sqlite_config(backup_dir, db_file)
        monkeypatch.setattr(db_backup, "config", config)

        db_backup.backup_sqlite()

        backups = list(backup_dir.glob("app_*.sqlite3"))
        assert len(backups) == 1
        assert checksum_path(backups[0]).exists()
        assert list(backup_dir.glob("*.partial")) == []

        result = sqlite3.connect(str(backups[0]))
        try:
            assert result.execute("SELECT id FROM items").fetchall() == [(42,)]
        finally:
            result.close()
    finally:
        writer.close()


def test_backup_sqlite_missing_source_fails_without_creating_file(monkeypatch, tmp_path):
    db_file = tmp_path / "missing.sqlite3"
    backup_dir = tmp_path / "backups"
    config = _mock_sqlite_config(backup_dir, db_file)
    monkeypatch.setattr(db_backup, "config", config)

    with pytest.raises(sqlite3.OperationalError):
        db_backup.backup_sqlite()

    assert not db_file.exists()
    assert list(backup_dir.glob("missing_*")) == []


def _sqlite_format_version_bytes(path):
    """Return header bytes 18-19 (file format write/read version).

    1 means a rollback-journal database, 2 means the file was last written
    in WAL mode.
    """
    with open(path, "rb") as f:
        f.seek(18)
        return f.read(2)


def test_backup_sqlite_from_wal_source_publishes_rollback_journal_file(monkeypatch, tmp_path):
    db_file = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(db_file)
    try:
        backup_dir = tmp_path / "backups"
        config = _mock_sqlite_config(backup_dir, db_file)
        monkeypatch.setattr(db_backup, "config", config)

        db_backup.backup_sqlite()

        backups = list(backup_dir.glob("app_*.sqlite3"))
        assert len(backups) == 1
        assert _sqlite_format_version_bytes(backups[0]) == b"\x01\x01"

        result = sqlite3.connect(str(backups[0]))
        try:
            assert result.execute("SELECT id FROM items").fetchall() == [(42,)]
        finally:
            result.close()

        assert list(backup_dir.glob("*-shm")) == []
        assert list(backup_dir.glob("*-wal")) == []
    finally:
        writer.close()


@POSIX_ONLY
def test_backup_sqlite_file_is_0600(monkeypatch, tmp_path):
    db_file = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(db_file)
    try:
        backup_dir = tmp_path / "backups"
        config = _mock_sqlite_config(backup_dir, db_file)
        monkeypatch.setattr(db_backup, "config", config)

        db_backup.backup_sqlite()

        backups = list(backup_dir.glob("app_*.sqlite3"))
        assert len(backups) == 1
        assert backups[0].stat().st_mode & 0o777 == 0o600
    finally:
        writer.close()
