from tests._init import *

import gzip
import io
import os
import re
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from _fake_pg_client import fake_client_command, missing_binary_command
from repom.config import PostgresTlsSettings
from repom.scripts import _backup_utils, db_backup
from repom.scripts._backup_utils import BackupError, checksum_path

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX file mode bits only")


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


def _use_fake_pg_dump(monkeypatch, stdout_bytes=10):
    """Route db_backup's pg_dump command through the real fake-client
    subprocess instead of a real pg_dump/docker binary, so tests exercise
    the actual Popen-based streaming path (see _fake_pg_client)."""
    monkeypatch.setattr(db_backup, "_pg_dump_command", lambda container_name: fake_client_command())
    monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", str(stdout_bytes))


def _read_echoed_env(env_sink):
    return dict(
        line.split("=", 1) for line in env_sink.read_text(encoding="utf-8").splitlines()
    )


def test_backup_postgresql_via_host_publishes_backup_and_checksum(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    db_backup.backup_postgresql_via_host()

    backups = list(tmp_path.glob("*.sql.gz"))
    assert len(backups) == 1
    assert backups[0].name.startswith(f"{config.postgres_db}_")
    assert checksum_path(backups[0]).exists()
    assert list(tmp_path.glob("*.partial")) == []


def test_backup_postgresql_via_host_names_backup_after_configured_database(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    db_backup.backup_postgresql_via_host()

    backups = list(tmp_path.glob("*.sql.gz"))
    assert len(backups) == 1
    assert re.fullmatch(r"repom_test_\d{8}_\d{6}\.sql\.gz", backups[0].name)


@POSIX_ONLY
def test_backup_directory_is_0700(monkeypatch, tmp_path):
    backup_dir = tmp_path / "backups"
    config = _mock_postgres_config(backup_dir)
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    db_backup.backup_postgresql_via_host()

    assert backup_dir.stat().st_mode & 0o777 == 0o700


@POSIX_ONLY
def test_backup_file_is_0600(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    db_backup.backup_postgresql_via_host()

    backups = list(tmp_path.glob("*.sql.gz"))
    assert len(backups) == 1
    assert backups[0].stat().st_mode & 0o777 == 0o600


def test_backup_raises_when_pg_dump_fails(monkeypatch, tmp_path):
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "pg_dump: connection failed")

    with pytest.raises(RuntimeError, match="pg_dump"):
        db_backup.backup_postgresql_via_host()

    assert list(tmp_path.glob("*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []


def test_backup_postgresql_via_host_does_not_delete_other_runs_partial_file(monkeypatch, tmp_path):
    """If another run (or a recent leftover) already owns the .partial path
    for this second, the O_EXCL creation fails and must not delete that
    other run's file (repom#153 round 3 fixed the same bug for SQLite;
    repom#167 review round 2 applies the same rule here)."""
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2024, 1, 1, 12, 0, 0)

    monkeypatch.setattr(db_backup, "datetime", _FixedDatetime)

    partial_path = tmp_path / "repom_test_20240101_120000.sql.gz.partial"
    partial_path.write_bytes(b"other run's in-progress data")

    with pytest.raises(BackupError):
        db_backup.backup_postgresql_via_host()

    assert partial_path.exists()
    assert partial_path.read_bytes() == b"other run's in-progress data"


def test_backup_postgresql_via_host_passes_tls_settings_in_env(monkeypatch, tmp_path):
    config = _mock_postgres_config(
        tmp_path, sslmode="verify-full", sslrootcert="/etc/ssl/certs/test-ca.pem"
    )
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)
    env_sink = tmp_path / "env.txt"
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_SINK", str(env_sink))
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_KEYS", "PGPASSWORD,PGSSLMODE,PGSSLROOTCERT")

    db_backup.backup_postgresql_via_host()

    env = _read_echoed_env(env_sink)
    assert env["PGPASSWORD"] == "test-password"
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/etc/ssl/certs/test-ca.pem"


def test_backup_postgresql_via_host_overrides_inherited_sslmode(monkeypatch, tmp_path):
    monkeypatch.setenv("PGSSLMODE", "disable")
    config = _mock_postgres_config(tmp_path, sslmode="require")
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)
    env_sink = tmp_path / "env.txt"
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_SINK", str(env_sink))
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_KEYS", "PGSSLMODE")

    db_backup.backup_postgresql_via_host()

    assert _read_echoed_env(env_sink)["PGSSLMODE"] == "require"


def test_backup_postgresql_via_host_raises_before_launching_process_on_invalid_tls(
    monkeypatch, tmp_path
):
    config = _mock_postgres_config(tmp_path)
    config.postgres_tls_settings.side_effect = ValueError(
        "PostgreSQL sslmode 'prefer' is not allowed in prod for a non-local host "
        "('db.example.com')"
    )
    monkeypatch.setattr(db_backup, "config", config)
    command_builder = MagicMock()
    monkeypatch.setattr(db_backup, "_pg_dump_command", command_builder)

    with pytest.raises(ValueError, match="sslmode") as exc_info:
        db_backup.backup_postgresql_via_host()

    command_builder.assert_not_called()
    assert list(tmp_path.glob("*.sql.gz")) == []
    assert "test-password" not in str(exc_info.value)


def _make_finished_backup(path, mtime):
    path.write_bytes(b"payload")
    os.utime(path, (mtime, mtime))


def test_backup_postgresql_via_host_rotation_does_not_delete_other_database_backup(
    monkeypatch, tmp_path
):
    """"repom" is a name-prefix of "repom_dev"; rotating "repom" backups with a
    plain glob like "repom_*.sql.gz" would also match "repom_dev_...", so a
    dev backup taken from the same checkout must not delete a prod backup."""
    dev_backup = tmp_path / "repom_dev_20260101_000000.sql.gz"
    _make_finished_backup(dev_backup, mtime=1)

    config = _mock_postgres_config(tmp_path)
    config.postgres_db = "repom"
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    db_backup.backup_postgresql_via_host()

    assert dev_backup.exists()
    new_backups = [p for p in tmp_path.glob("*.sql.gz") if p != dev_backup]
    assert len(new_backups) == 1
    assert re.fullmatch(r"repom_\d{8}_\d{6}\.sql\.gz", new_backups[0].name)


def test_backup_postgresql_via_host_rotation_keeps_max_backups_per_database(
    monkeypatch, tmp_path
):
    """Three existing prod backups at the retention limit, plus three dev
    backups sharing the directory, must rotate independently: the oldest prod
    backup is removed while every dev backup survives."""
    prod_backups = [
        tmp_path / f"repom_2026010{n}_000000.sql.gz" for n in range(1, 4)
    ]
    for i, path in enumerate(prod_backups, start=1):
        _make_finished_backup(path, mtime=i)

    dev_backups = [
        tmp_path / f"repom_dev_2026010{n}_000000.sql.gz" for n in range(1, 4)
    ]
    for i, path in enumerate(dev_backups, start=1):
        _make_finished_backup(path, mtime=i)

    config = _mock_postgres_config(tmp_path)
    config.postgres_db = "repom"
    monkeypatch.setattr(db_backup, "config", config)
    _use_fake_pg_dump(monkeypatch)

    db_backup.backup_postgresql_via_host()

    assert not prod_backups[0].exists()
    assert prod_backups[1].exists() and prod_backups[2].exists()
    assert all(path.exists() for path in dev_backups)
    remaining_prod = [p for p in tmp_path.glob("repom_*.sql.gz") if p not in dev_backups]
    assert len(remaining_prod) == db_backup.MAX_BACKUPS_PER_DB


class TestStreamingWithoutDeadlock:
    """Exercises the real Popen-based streaming path end to end (repom#167):
    a child writing more to stderr than an OS pipe buffer holds must never
    deadlock the backup, for either the host or the Docker command shape."""

    def _run(self, monkeypatch, tmp_path, container_running):
        config = _mock_postgres_config(tmp_path)
        config.db_type = "postgres"
        monkeypatch.setattr(db_backup, "config", config)
        monkeypatch.setattr(
            _backup_utils, "is_container_running", MagicMock(return_value=container_running)
        )
        monkeypatch.setattr(
            db_backup.DockerCommandExecutor,
            "exec_command",
            MagicMock(side_effect=AssertionError("exec_command must not carry the dump payload")),
        )
        monkeypatch.setattr(db_backup, "_pg_dump_command", lambda container_name: fake_client_command())
        monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", str(1024 * 1024))
        monkeypatch.setenv("FAKE_CHILD_STDERR_BYTES", str(1024 * 1024))

        db_backup.main()

        backups = list(tmp_path.glob("*.sql.gz"))
        assert len(backups) == 1
        with gzip.open(backups[0], "rb") as f:
            assert len(f.read()) == 1024 * 1024

    def test_host_backup_path(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, container_running=False)

    def test_docker_backup_path_never_calls_exec_command(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, container_running=True)


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

    with pytest.raises(BackupError) as exc_info:
        db_backup.backup_sqlite()

    assert isinstance(exc_info.value.__cause__, sqlite3.OperationalError)
    assert not db_file.exists()
    assert list(backup_dir.glob("missing_*")) == []


def test_backup_sqlite_does_not_delete_other_runs_partial_file(monkeypatch, tmp_path):
    db_file = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(db_file)
    try:
        backup_dir = tmp_path / "backups"
        config = _mock_sqlite_config(backup_dir, db_file)
        monkeypatch.setattr(db_backup, "config", config)

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2024, 1, 1, 12, 0, 0)

        monkeypatch.setattr(db_backup, "datetime", _FixedDatetime)

        backup_dir.mkdir(parents=True)
        partial_path = backup_dir / "app_20240101_120000.sqlite3.partial"
        partial_path.write_bytes(b"other run's in-progress data")

        with pytest.raises(BackupError):
            db_backup.backup_sqlite()

        assert partial_path.exists()
        assert partial_path.read_bytes() == b"other run's in-progress data"
    finally:
        writer.close()


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


def test_backup_sqlite_rotation_does_not_delete_other_database_backup(monkeypatch, tmp_path):
    """"repom" is a name-prefix of "repom_dev"; rotating "repom" backups with a
    plain glob like "repom_*.sqlite3" would also match "repom_dev_...", so a
    dev backup taken from the same checkout must not delete a prod backup."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    dev_backup = backup_dir / "repom_dev_20260101_000000.sqlite3"
    _make_finished_backup(dev_backup, mtime=1)

    db_file = tmp_path / "repom.sqlite3"
    writer = sqlite3.connect(str(db_file))
    writer.execute("CREATE TABLE items (id INTEGER)")
    writer.commit()
    config = _mock_sqlite_config(backup_dir, db_file)
    monkeypatch.setattr(db_backup, "config", config)

    try:
        db_backup.backup_sqlite()
    finally:
        writer.close()

    assert dev_backup.exists()
    new_backups = [p for p in backup_dir.glob("*.sqlite3") if p != dev_backup]
    assert len(new_backups) == 1
    assert re.fullmatch(r"repom_\d{8}_\d{6}\.sqlite3", new_backups[0].name)


def test_backup_sqlite_rotation_keeps_max_backups_per_database(monkeypatch, tmp_path):
    """Three existing prod backups at the retention limit, plus three dev
    backups sharing the directory, must rotate independently: the oldest prod
    backup is removed while every dev backup survives."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    prod_backups = [
        backup_dir / f"repom_2026010{n}_000000.sqlite3" for n in range(1, 4)
    ]
    for i, path in enumerate(prod_backups, start=1):
        _make_finished_backup(path, mtime=i)

    dev_backups = [
        backup_dir / f"repom_dev_2026010{n}_000000.sqlite3" for n in range(1, 4)
    ]
    for i, path in enumerate(dev_backups, start=1):
        _make_finished_backup(path, mtime=i)

    db_file = tmp_path / "repom.sqlite3"
    writer = sqlite3.connect(str(db_file))
    writer.execute("CREATE TABLE items (id INTEGER)")
    writer.commit()
    config = _mock_sqlite_config(backup_dir, db_file)
    monkeypatch.setattr(db_backup, "config", config)

    try:
        db_backup.backup_sqlite()
    finally:
        writer.close()

    assert not prod_backups[0].exists()
    assert prod_backups[1].exists() and prod_backups[2].exists()
    assert all(path.exists() for path in dev_backups)
    remaining_prod = [p for p in backup_dir.glob("repom_*.sqlite3") if p not in dev_backups]
    assert len(remaining_prod) == db_backup.MAX_BACKUPS_PER_DB


def _mock_postgres_config_for_main(backup_dir, sslmode="prefer", sslrootcert=None):
    config = _mock_postgres_config(backup_dir, sslmode=sslmode, sslrootcert=sslrootcert)
    config.db_type = "postgres"
    return config


def test_main_raises_backup_error_when_host_pg_dump_fails(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    _use_fake_pg_dump(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "pg_dump: connection failed")

    with pytest.raises(BackupError, match="pg_dump"):
        db_backup.main()

    assert list(tmp_path.glob("*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []


def test_main_raises_backup_error_when_docker_pg_dump_fails(monkeypatch, tmp_path):
    """Also proves the Docker backup path never falls back to
    DockerCommandExecutor.exec_command for the dump payload (repom#167):
    exec_command is poisoned to fail, yet the failure is still correctly
    reported as a pg_dump error through the Popen-based streaming path."""
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=True))
    monkeypatch.setattr(
        db_backup.DockerCommandExecutor,
        "exec_command",
        MagicMock(side_effect=AssertionError("exec_command must not carry the dump payload")),
    )
    _use_fake_pg_dump(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "pg_dump: connection failed")

    with pytest.raises(BackupError, match="pg_dump"):
        db_backup.main()

    assert list(tmp_path.glob("*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []


def test_main_raises_backup_error_when_pg_dump_missing(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(db_backup, "_pg_dump_command", lambda container_name: missing_binary_command())

    with pytest.raises(BackupError, match="pg_dump"):
        db_backup.main()


class _FailingWriter(io.RawIOBase):
    """Raises OSError partway through, simulating a full disk mid-backup."""

    def __init__(self, fail_after=1):
        super().__init__()
        self._writes = 0
        self._fail_after = fail_after

    def writable(self):
        return True

    def write(self, data):
        self._writes += 1
        if self._writes > self._fail_after:
            raise OSError("disk full")
        return len(data)


def test_main_raises_backup_error_on_write_error_while_compressing(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    _use_fake_pg_dump(monkeypatch, stdout_bytes=500_000)
    monkeypatch.setattr(db_backup, "open_backup_temp_file", lambda path: _FailingWriter())

    with pytest.raises(BackupError, match="disk full"):
        db_backup.main()

    assert list(tmp_path.glob("*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []


def test_main_raises_backup_error_on_empty_dump_output_via_host(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    _use_fake_pg_dump(monkeypatch, stdout_bytes=0)

    with pytest.raises(BackupError, match="empty"):
        db_backup.main()

    assert list(tmp_path.glob("*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []


def test_main_raises_backup_error_on_empty_dump_output_via_docker(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=True))
    monkeypatch.setattr(
        db_backup.DockerCommandExecutor,
        "exec_command",
        MagicMock(side_effect=AssertionError("exec_command must not carry the dump payload")),
    )
    _use_fake_pg_dump(monkeypatch, stdout_bytes=0)

    with pytest.raises(BackupError, match="empty"):
        db_backup.main()

    assert list(tmp_path.glob("*.sql.gz")) == []
    assert list(tmp_path.glob("*.partial")) == []


def test_main_returns_normally_on_successful_backup(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_backup, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    _use_fake_pg_dump(monkeypatch)

    db_backup.main()

    assert len(list(tmp_path.glob("*.sql.gz"))) == 1


def _mock_sqlite_config_for_main(backup_dir, db_file_path):
    config = _mock_sqlite_config(backup_dir, db_file_path)
    config.db_type = "sqlite"
    return config


def test_main_raises_backup_error_when_sqlite_source_missing(monkeypatch, tmp_path):
    db_file = tmp_path / "missing.sqlite3"
    backup_dir = tmp_path / "backups"
    config = _mock_sqlite_config_for_main(backup_dir, db_file)
    monkeypatch.setattr(db_backup, "config", config)

    with pytest.raises(BackupError) as exc_info:
        db_backup.main()

    assert isinstance(exc_info.value.__cause__, sqlite3.OperationalError)
    assert list(backup_dir.glob("missing_*")) == []
