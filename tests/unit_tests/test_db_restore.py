from tests._init import *

import gzip
import io
from unittest.mock import MagicMock

import pytest

from repom.scripts import db_restore
from repom.scripts._backup_utils import ChecksumError, write_checksum


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


def _mock_postgres_config(backup_dir):
    config = MagicMock()
    config.db_backup_path = str(backup_dir)
    config.postgres.host = "localhost"
    config.postgres.port = 5432
    config.postgres.user = "postgres"
    config.postgres.password = "test-password"
    config.postgres_db = "repom_test"
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

    with pytest.raises(ChecksumError):
        db_restore.restore_postgresql_via_host(backup_file)


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
