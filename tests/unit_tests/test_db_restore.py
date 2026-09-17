from tests._init import *

import gzip
import io
import sqlite3
import subprocess
from unittest.mock import MagicMock

import pytest

from repom.config import PostgresTlsSettings
from repom.scripts import _backup_utils, db_restore
from repom.scripts._backup_utils import ChecksumError, RestoreError, checksum_path, write_checksum


class _FakeProc:
    """Stand-in for subprocess.Popen covering the gunzip/psql restore pipeline."""

    def __init__(self, returncode=0, stderr_bytes=b""):
        self.returncode = returncode
        self._stderr_bytes = stderr_bytes
        self.stderr = io.BytesIO(stderr_bytes)
        self.stdout = io.BytesIO(b"")
        self.waited = False

    def communicate(self):
        return b"", self._stderr_bytes

    def wait(self):
        self.waited = True
        return self.returncode


def _make_popen(gunzip_returncode=0, gunzip_stderr=b"", psql_returncode=0, psql_stderr=b""):
    def _popen(cmd, **kwargs):
        if cmd[0] == "gunzip":
            return _FakeProc(returncode=gunzip_returncode, stderr_bytes=gunzip_stderr)
        if cmd[0] == "psql":
            return _FakeProc(returncode=psql_returncode, stderr_bytes=psql_stderr)
        raise AssertionError(f"unexpected command: {cmd}")

    return _popen


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


def _make_backup_file(tmp_path, name="db_20260101_000000.sql.gz", payload=b"SELECT 1;\n"):
    backup_file = tmp_path / name
    with gzip.open(backup_file, "wb") as f:
        f.write(payload)
    return backup_file


def test_restore_raises_when_gunzip_fails(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(
        db_restore.subprocess,
        "Popen",
        _make_popen(gunzip_returncode=1, gunzip_stderr=b"gzip: unexpected end of file", psql_returncode=0),
    )

    with pytest.raises(RuntimeError, match="gunzip"):
        db_restore.restore_postgresql_via_host(backup_file)


def test_restore_raises_when_psql_fails(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(
        db_restore.subprocess,
        "Popen",
        _make_popen(gunzip_returncode=0, psql_returncode=1, psql_stderr=b"psql: FATAL"),
    )

    with pytest.raises(RuntimeError, match="psql"):
        db_restore.restore_postgresql_via_host(backup_file)


def test_restore_succeeds_when_both_processes_exit_zero(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen())

    db_restore.restore_postgresql_via_host(backup_file)


def test_restore_verifies_checksum_and_raises_on_mismatch(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    write_checksum(backup_file)

    # Corrupt the file after recording its checksum.
    with gzip.open(backup_file, "ab") as f:
        f.write(b"DROP TABLE users;\n")

    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen())

    with pytest.raises(RestoreError) as exc_info:
        db_restore.restore_postgresql_via_host(backup_file)

    assert isinstance(exc_info.value.__cause__, ChecksumError)


def test_restore_succeeds_when_checksum_matches(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    write_checksum(backup_file)

    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen())

    db_restore.restore_postgresql_via_host(backup_file)


def test_restore_warns_but_proceeds_when_checksum_is_missing(monkeypatch, tmp_path, capsys):
    backup_file = _make_backup_file(tmp_path)

    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen())

    db_restore.restore_postgresql_via_host(backup_file)

    captured = capsys.readouterr()
    assert "no checksum recorded" in captured.out.lower()


def _make_recording_popen(popen_calls):
    def _popen(cmd, **kwargs):
        popen_calls.append((cmd, kwargs))
        return _FakeProc()

    return _popen


def test_restore_postgresql_via_host_passes_tls_settings_in_env(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(
        tmp_path, sslmode="verify-full", sslrootcert="/etc/ssl/certs/test-ca.pem"
    )
    monkeypatch.setattr(db_restore, "config", config)
    popen_calls = []
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_recording_popen(popen_calls))

    db_restore.restore_postgresql_via_host(backup_file)

    psql_cmd, psql_kwargs = next(call for call in popen_calls if call[0][0] == "psql")
    assert psql_kwargs["env"]["PGPASSWORD"] == "test-password"
    assert psql_kwargs["env"]["PGSSLMODE"] == "verify-full"
    assert psql_kwargs["env"]["PGSSLROOTCERT"] == "/etc/ssl/certs/test-ca.pem"


def test_restore_postgresql_via_host_overrides_inherited_sslmode(monkeypatch, tmp_path):
    monkeypatch.setenv("PGSSLMODE", "disable")
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path, sslmode="require")
    monkeypatch.setattr(db_restore, "config", config)
    popen_calls = []
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_recording_popen(popen_calls))

    db_restore.restore_postgresql_via_host(backup_file)

    psql_cmd, psql_kwargs = next(call for call in popen_calls if call[0][0] == "psql")
    assert psql_kwargs["env"]["PGSSLMODE"] == "require"


def test_restore_postgresql_via_host_raises_before_launching_process_on_invalid_tls(
    monkeypatch, tmp_path
):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    config.postgres_tls_settings.side_effect = ValueError(
        "PostgreSQL sslmode 'prefer' is not allowed in prod for a non-local host "
        "('db.example.com')"
    )
    monkeypatch.setattr(db_restore, "config", config)
    popen_calls = []
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_recording_popen(popen_calls))

    with pytest.raises(ValueError, match="sslmode") as exc_info:
        db_restore.restore_postgresql_via_host(backup_file)

    assert popen_calls == []
    assert "test-password" not in str(exc_info.value)


def _mock_sqlite_config(backup_dir, db_file_path):
    config = MagicMock()
    config.db_backup_path = str(backup_dir)
    config.sqlite.db_file_path = str(db_file_path)
    return config


def _make_sqlite_db(path, row_id, table="items"):
    conn = sqlite3.connect(str(path))
    conn.execute(f"CREATE TABLE {table} (id INTEGER)")
    conn.execute(f"INSERT INTO {table} VALUES (?)", (row_id,))
    conn.commit()
    return conn


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


def test_restore_sqlite_visible_to_open_connection_after_next_query(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    other_conn = _make_sqlite_db(current_db, row_id=1)
    try:
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "app_20260101_000000.sqlite3"
        restore_source = _make_sqlite_db(backup_file, row_id=99)
        restore_source.close()
        write_checksum(backup_file)

        config = _mock_sqlite_config(backup_dir, current_db)
        monkeypatch.setattr(db_restore, "config", config)

        db_restore.restore_sqlite(backup_file)

        assert other_conn.execute("SELECT id FROM items").fetchall() == [(99,)]
    finally:
        other_conn.close()


def test_restore_sqlite_pre_restore_snapshot_includes_uncheckpointed_wal_data(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(current_db, row_id=42)
    try:
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "app_20260101_000000.sqlite3"
        restore_source = _make_sqlite_db(backup_file, row_id=99)
        restore_source.close()
        write_checksum(backup_file)

        config = _mock_sqlite_config(backup_dir, current_db)
        monkeypatch.setattr(db_restore, "config", config)

        db_restore.restore_sqlite(backup_file)

        snapshots = list(backup_dir.glob("restore_backup_*.sqlite3"))
        assert len(snapshots) == 1
        assert checksum_path(snapshots[0]).exists()

        snapshot_conn = sqlite3.connect(str(snapshots[0]))
        try:
            assert snapshot_conn.execute("SELECT id FROM items").fetchall() == [(42,)]
        finally:
            snapshot_conn.close()
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


def test_restore_sqlite_pre_restore_snapshot_publishes_rollback_journal_file(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(current_db, row_id=42)
    try:
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "app_20260101_000000.sqlite3"
        restore_source = _make_sqlite_db(backup_file, row_id=99)
        restore_source.close()
        write_checksum(backup_file)

        config = _mock_sqlite_config(backup_dir, current_db)
        monkeypatch.setattr(db_restore, "config", config)

        db_restore.restore_sqlite(backup_file)

        snapshots = list(backup_dir.glob("restore_backup_*.sqlite3"))
        assert len(snapshots) == 1
        assert _sqlite_format_version_bytes(snapshots[0]) == b"\x01\x01"

        snapshot_conn = sqlite3.connect(str(snapshots[0]))
        try:
            snapshot_conn.execute("SELECT id FROM items").fetchall()
        finally:
            snapshot_conn.close()

        assert list(backup_dir.glob("*-shm")) == []
        assert list(backup_dir.glob("*-wal")) == []
    finally:
        writer.close()


def test_restore_sqlite_from_wal_flagged_backup_leaves_no_sidecars(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    live_conn = _make_sqlite_db(current_db, row_id=1)
    try:
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "app_20260101_000000.sqlite3"

        # A legacy WAL-flagged backup: created directly with journal_mode=WAL
        # and closed, mirroring a backup published before this fix.
        wal_conn = sqlite3.connect(str(backup_file))
        wal_conn.execute("PRAGMA journal_mode=WAL")
        wal_conn.execute("CREATE TABLE items (id INTEGER)")
        wal_conn.execute("INSERT INTO items VALUES (99)")
        wal_conn.commit()
        wal_conn.close()
        write_checksum(backup_file)

        config = _mock_sqlite_config(backup_dir, current_db)
        monkeypatch.setattr(db_restore, "config", config)

        db_restore.restore_sqlite(backup_file)

        assert list(backup_dir.glob("*-shm")) == []
        assert list(backup_dir.glob("*-wal")) == []
    finally:
        live_conn.close()


def test_restore_sqlite_into_live_wal_database_keeps_wal_mode_and_reaches_open_writer(
    monkeypatch, tmp_path
):
    current_db = tmp_path / "app.sqlite3"
    writer = _make_wal_db_with_uncheckpointed_row(current_db, row_id=1)
    try:
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "app_20260101_000000.sqlite3"
        restore_source = _make_sqlite_db(backup_file, row_id=99)
        restore_source.close()
        write_checksum(backup_file)

        config = _mock_sqlite_config(backup_dir, current_db)
        monkeypatch.setattr(db_restore, "config", config)

        db_restore.restore_sqlite(backup_file)

        assert writer.execute("SELECT id FROM items").fetchall() == [(99,)]
        assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

        fresh_conn = sqlite3.connect(str(current_db))
        try:
            assert fresh_conn.execute("SELECT id FROM items").fetchall() == [(99,)]
            assert fresh_conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        finally:
            fresh_conn.close()
    finally:
        writer.close()


def test_restore_sqlite_aborts_on_checksum_mismatch_without_touching_db(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    live_conn = _make_sqlite_db(current_db, row_id=1)
    try:
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "app_20260101_000000.sqlite3"
        restore_source = _make_sqlite_db(backup_file, row_id=99)
        restore_source.close()
        write_checksum(backup_file)

        # Corrupt the file after recording its checksum.
        with open(backup_file, "ab") as f:
            f.write(b"garbage")

        config = _mock_sqlite_config(backup_dir, current_db)
        monkeypatch.setattr(db_restore, "config", config)

        with pytest.raises(RestoreError) as exc_info:
            db_restore.restore_sqlite(backup_file)

        assert isinstance(exc_info.value.__cause__, ChecksumError)
        assert live_conn.execute("SELECT id FROM items").fetchall() == [(1,)]
        assert list(backup_dir.glob("restore_backup_*.sqlite3")) == []
    finally:
        live_conn.close()


def _mock_postgres_config_for_main(backup_dir, sslmode="prefer", sslrootcert=None):
    config = _mock_postgres_config(backup_dir, sslmode=sslmode, sslrootcert=sslrootcert)
    config.db_type = "postgres"
    return config


def _make_popen_missing(missing_cmd):
    def _popen(cmd, **kwargs):
        if cmd[0] == missing_cmd:
            raise FileNotFoundError(missing_cmd)
        return _FakeProc()

    return _popen


def test_main_raises_restore_error_when_host_psql_fails(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(
        db_restore.subprocess,
        "Popen",
        _make_popen(psql_returncode=1, psql_stderr=b"psql: FATAL"),
    )
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError, match="psql"):
        db_restore.main()


def test_main_raises_restore_error_when_docker_psql_fails(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=True))
    monkeypatch.setattr(
        db_restore.DockerCommandExecutor,
        "exec_command",
        MagicMock(
            side_effect=subprocess.CalledProcessError(1, ["psql"], stderr=b"psql: FATAL")
        ),
    )
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError, match="psql"):
        db_restore.main()


def test_main_raises_restore_error_when_gunzip_missing(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen_missing("gunzip"))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError):
        db_restore.main()


def test_main_raises_restore_error_when_psql_missing(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen_missing("psql"))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError):
        db_restore.main()


def test_main_raises_restore_error_on_checksum_mismatch(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    write_checksum(backup_file)
    with gzip.open(backup_file, "ab") as f:
        f.write(b"DROP TABLE users;\n")

    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen())
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError) as exc_info:
        db_restore.main()

    assert isinstance(exc_info.value.__cause__, ChecksumError)


def test_main_raises_restore_error_when_backup_directory_missing(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path / "missing")
    monkeypatch.setattr(db_restore, "config", config)

    with pytest.raises(RestoreError, match="not found"):
        db_restore.main()


def test_main_raises_restore_error_when_no_backups_found(monkeypatch, tmp_path):
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)

    with pytest.raises(RestoreError, match="No backups"):
        db_restore.main()


def test_main_returns_normally_on_successful_restore(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(db_restore.subprocess, "Popen", _make_popen())
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    db_restore.main()


def test_main_returns_normally_when_restore_cancelled_at_selection(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["q"]))

    db_restore.main()


def test_main_returns_normally_when_restore_cancelled_at_confirmation(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "n"]))

    db_restore.main()


def _mock_sqlite_config_for_main(backup_dir, db_file_path):
    config = _mock_sqlite_config(backup_dir, db_file_path)
    config.db_type = "sqlite"
    return config


def test_main_raises_restore_error_on_sqlite_checksum_mismatch(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_file = backup_dir / "app_20260101_000000.sqlite3"
    restore_source = _make_sqlite_db(backup_file, row_id=99)
    restore_source.close()
    write_checksum(backup_file)

    # Corrupt the file after recording its checksum.
    with open(backup_file, "ab") as f:
        f.write(b"garbage")

    config = _mock_sqlite_config_for_main(backup_dir, current_db)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError) as exc_info:
        db_restore.main()

    assert isinstance(exc_info.value.__cause__, ChecksumError)
