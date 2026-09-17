from tests._init import *

import gzip
import sqlite3
from unittest.mock import MagicMock

import pytest

from _fake_pg_client import fake_client_command, missing_binary_command
from repom.config import PostgresTlsSettings
from repom.scripts import _backup_utils, db_restore
from repom.scripts._backup_utils import ChecksumError, RestoreError, checksum_path, write_checksum


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


def _make_backup_file(tmp_path, name="repom_test_20260101_000000.sql.gz", payload=b"SELECT 1;\n"):
    backup_file = tmp_path / name
    with gzip.open(backup_file, "wb") as f:
        f.write(payload)
    return backup_file


def _use_fake_psql(monkeypatch):
    """Route db_restore's psql command through the real fake-client
    subprocess instead of a real psql/docker binary, so tests exercise the
    actual Popen-based streaming path (see _fake_pg_client)."""
    monkeypatch.setattr(db_restore, "_psql_command", lambda container_name: fake_client_command())


def _read_echoed_env(env_sink):
    return dict(
        line.split("=", 1) for line in env_sink.read_text(encoding="utf-8").splitlines()
    )


def test_restore_raises_when_psql_fails(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "psql: FATAL")

    with pytest.raises(RuntimeError, match="psql"):
        db_restore.restore_postgresql_via_host(backup_file)


def test_restore_reports_psql_error_when_psql_exits_before_reading_all_stdin(monkeypatch, tmp_path):
    """When psql stops reading stdin and exits with an error (ON_ERROR_STOP
    failure, auth failure, missing role) while a large backup is still being
    streamed in, the restore must surface psql's real error, not a raised
    BrokenPipeError (repom#167 review round 2)."""
    payload = b"INSERT INTO t VALUES (1);\n" * 1_000_000  # well over 20 MB
    backup_file = _make_backup_file(tmp_path, payload=payload)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "3")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "ERROR: relation does not exist\n")

    with pytest.raises(RestoreError, match="relation does not exist"):
        db_restore.restore_postgresql_via_host(backup_file)


def test_restore_succeeds_when_psql_exits_zero(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)

    db_restore.restore_postgresql_via_host(backup_file)


def test_restore_postgresql_via_host_delivers_exact_decompressed_bytes_to_psql_stdin(
    monkeypatch, tmp_path
):
    """The restore must stream gzip.open(backup_file) straight into psql's
    stdin, byte for byte, without shelling out to an external gunzip
    (repom#167)."""
    payload = b"INSERT INTO t VALUES (1);\n" * 10_000
    backup_file = _make_backup_file(tmp_path, payload=payload)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)
    sink_path = tmp_path / "stdin_echo.bin"
    monkeypatch.setenv("FAKE_CHILD_STDIN_SINK", str(sink_path))

    db_restore.restore_postgresql_via_host(backup_file)

    assert sink_path.read_bytes() == payload


def test_restore_verifies_checksum_and_raises_on_mismatch(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    write_checksum(backup_file)

    # Corrupt the file after recording its checksum.
    with gzip.open(backup_file, "ab") as f:
        f.write(b"DROP TABLE users;\n")

    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    psql_command = MagicMock()
    monkeypatch.setattr(db_restore, "_psql_command", psql_command)

    with pytest.raises(RestoreError) as exc_info:
        db_restore.restore_postgresql_via_host(backup_file)

    assert isinstance(exc_info.value.__cause__, ChecksumError)
    psql_command.assert_not_called()


def test_restore_succeeds_when_checksum_matches(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    write_checksum(backup_file)

    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)

    db_restore.restore_postgresql_via_host(backup_file)


def test_restore_warns_but_proceeds_when_checksum_is_missing(monkeypatch, tmp_path, capsys):
    backup_file = _make_backup_file(tmp_path)

    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)

    db_restore.restore_postgresql_via_host(backup_file)

    captured = capsys.readouterr()
    assert "no checksum recorded" in captured.out.lower()


def test_restore_postgresql_via_host_raises_when_psql_missing(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(db_restore, "_psql_command", lambda container_name: missing_binary_command())

    with pytest.raises(RestoreError):
        db_restore.restore_postgresql_via_host(backup_file)


def test_restore_postgresql_via_host_passes_tls_settings_in_env(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(
        tmp_path, sslmode="verify-full", sslrootcert="/etc/ssl/certs/test-ca.pem"
    )
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)
    env_sink = tmp_path / "env.txt"
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_SINK", str(env_sink))
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_KEYS", "PGPASSWORD,PGSSLMODE,PGSSLROOTCERT")

    db_restore.restore_postgresql_via_host(backup_file)

    env = _read_echoed_env(env_sink)
    assert env["PGPASSWORD"] == "test-password"
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/etc/ssl/certs/test-ca.pem"


def test_restore_postgresql_via_host_overrides_inherited_sslmode(monkeypatch, tmp_path):
    monkeypatch.setenv("PGSSLMODE", "disable")
    backup_file = _make_backup_file(tmp_path)
    config = _mock_postgres_config(tmp_path, sslmode="require")
    monkeypatch.setattr(db_restore, "config", config)
    _use_fake_psql(monkeypatch)
    env_sink = tmp_path / "env.txt"
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_SINK", str(env_sink))
    monkeypatch.setenv("FAKE_CHILD_ECHO_ENV_KEYS", "PGSSLMODE")

    db_restore.restore_postgresql_via_host(backup_file)

    assert _read_echoed_env(env_sink)["PGSSLMODE"] == "require"


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
    psql_command = MagicMock()
    monkeypatch.setattr(db_restore, "_psql_command", psql_command)

    with pytest.raises(ValueError, match="sslmode") as exc_info:
        db_restore.restore_postgresql_via_host(backup_file)

    psql_command.assert_not_called()
    assert "test-password" not in str(exc_info.value)


class TestRestoreStreamingWithoutDeadlock:
    """Exercises the real Popen-based streaming path end to end (repom#167):
    a child writing more to stderr than an OS pipe buffer holds must never
    deadlock the restore, for either the host or the Docker command shape,
    and the payload never passes through DockerCommandExecutor.exec_command."""

    def _run(self, monkeypatch, tmp_path, container_running):
        payload = b"X" * (1024 * 1024)
        backup_file = _make_backup_file(tmp_path, payload=payload)
        config = _mock_postgres_config_for_main(tmp_path)
        monkeypatch.setattr(db_restore, "config", config)
        monkeypatch.setattr(
            _backup_utils, "is_container_running", MagicMock(return_value=container_running)
        )
        monkeypatch.setattr(
            db_restore.DockerCommandExecutor,
            "exec_command",
            MagicMock(side_effect=AssertionError("exec_command must not carry the restore payload")),
        )
        _use_fake_psql(monkeypatch)
        sink_path = tmp_path / "stdin_echo.bin"
        monkeypatch.setenv("FAKE_CHILD_STDIN_SINK", str(sink_path))
        monkeypatch.setenv("FAKE_CHILD_STDERR_BYTES", str(1024 * 1024))
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

        db_restore.main()

        assert sink_path.read_bytes() == payload

    def test_host_restore_path(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, container_running=False)

    def test_docker_restore_path_never_calls_exec_command(self, monkeypatch, tmp_path):
        self._run(monkeypatch, tmp_path, container_running=True)


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


def test_main_raises_restore_error_when_host_psql_fails(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    _use_fake_psql(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "psql: FATAL")
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError, match="psql"):
        db_restore.main()


def test_main_raises_restore_error_when_docker_psql_fails(monkeypatch, tmp_path):
    """Also proves the Docker restore path never falls back to
    DockerCommandExecutor.exec_command for the restore payload (repom#167):
    exec_command is poisoned to fail, yet the failure is still correctly
    reported as a psql error through the Popen-based streaming path."""
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=True))
    monkeypatch.setattr(
        db_restore.DockerCommandExecutor,
        "exec_command",
        MagicMock(side_effect=AssertionError("exec_command must not carry the restore payload")),
    )
    _use_fake_psql(monkeypatch)
    monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")
    monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "psql: FATAL")
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError, match="psql"):
        db_restore.main()


def test_main_raises_restore_error_when_psql_missing(monkeypatch, tmp_path):
    _make_backup_file(tmp_path)
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    monkeypatch.setattr(db_restore, "_psql_command", lambda container_name: missing_binary_command())
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError):
        db_restore.main()


def test_main_raises_restore_error_on_truncated_backup_before_launching_psql(monkeypatch, tmp_path):
    """A truncated gzip archive must fail before psql is ever started, not
    partway through applying it (repom#167)."""
    backup_file = _make_backup_file(tmp_path, payload=b"SELECT 1;\n" * 1000)
    backup_file.write_bytes(backup_file.read_bytes()[:-5])
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    psql_command = MagicMock()
    monkeypatch.setattr(db_restore, "_psql_command", psql_command)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError):
        db_restore.main()

    psql_command.assert_not_called()


def test_main_raises_restore_error_on_checksum_mismatch(monkeypatch, tmp_path):
    backup_file = _make_backup_file(tmp_path)
    write_checksum(backup_file)
    with gzip.open(backup_file, "ab") as f:
        f.write(b"DROP TABLE users;\n")

    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    psql_command = MagicMock()
    monkeypatch.setattr(db_restore, "_psql_command", psql_command)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    with pytest.raises(RestoreError) as exc_info:
        db_restore.main()

    assert isinstance(exc_info.value.__cause__, ChecksumError)
    psql_command.assert_not_called()


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
    _use_fake_psql(monkeypatch)
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


def test_main_cancels_cross_database_restore_when_target_name_not_typed(monkeypatch, tmp_path):
    """A backup from another database ("otherdb") must not be restorable by
    typing "y"; only typing the target database name confirms the restore."""
    _make_backup_file(tmp_path, name="otherdb_20260101_000000.sql.gz")
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    psql_command = MagicMock()
    monkeypatch.setattr(db_restore, "_psql_command", psql_command)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    db_restore.main()

    psql_command.assert_not_called()


def test_main_proceeds_with_cross_database_restore_when_target_name_typed(monkeypatch, tmp_path):
    _make_backup_file(tmp_path, name="otherdb_20260101_000000.sql.gz")
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    _use_fake_psql(monkeypatch)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "repom_test"]))

    db_restore.main()


def test_main_cancels_legacy_backup_restore_when_target_name_not_typed(monkeypatch, tmp_path):
    """A legacy ``db_<timestamp>.sql.gz`` backup has an unknown source
    database, so it must require typing the target name too."""
    _make_backup_file(tmp_path, name="db_20260101_000000.sql.gz")
    config = _mock_postgres_config_for_main(tmp_path)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr(_backup_utils, "is_container_running", MagicMock(return_value=False))
    psql_command = MagicMock()
    monkeypatch.setattr(db_restore, "_psql_command", psql_command)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    db_restore.main()

    psql_command.assert_not_called()


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


def test_main_cancels_sqlite_cross_database_restore_when_target_name_not_typed(monkeypatch, tmp_path):
    """A backup from another database ("other") must not be restorable by
    typing "y"; only typing the target database name ("app") confirms it."""
    current_db = tmp_path / "app.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_file = backup_dir / "other_20260101_000000.sqlite3"
    restore_source = _make_sqlite_db(backup_file, row_id=99)
    restore_source.close()
    write_checksum(backup_file)

    config = _mock_sqlite_config_for_main(backup_dir, current_db)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "y"]))

    db_restore.main()

    assert not current_db.exists()


def test_main_proceeds_with_sqlite_cross_database_restore_when_target_name_typed(monkeypatch, tmp_path):
    current_db = tmp_path / "app.sqlite3"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_file = backup_dir / "other_20260101_000000.sqlite3"
    restore_source = _make_sqlite_db(backup_file, row_id=99)
    restore_source.close()
    write_checksum(backup_file)

    config = _mock_sqlite_config_for_main(backup_dir, current_db)
    monkeypatch.setattr(db_restore, "config", config)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["1", "app"]))

    db_restore.main()

    assert current_db.exists()
