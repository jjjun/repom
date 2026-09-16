from tests._init import *

import os
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
