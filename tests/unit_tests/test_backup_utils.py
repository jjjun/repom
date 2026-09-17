from tests._init import *

import gzip
import io
import subprocess
import sys
from unittest.mock import MagicMock
import os
import time

import pytest
from basekit.docker_manager import DockerCommandExecutor

from _fake_pg_client import fake_client_command, missing_binary_command
from repom.docker_service import DockerUnavailableError
from repom.scripts import _backup_utils
from repom.scripts._backup_utils import (
    BackupError,
    ByteCountingWriter,
    ChecksumError,
    backup_name_pattern,
    build_pg_client_command,
    checksum_path,
    cleanup_incomplete_backups,
    compute_checksum,
    ensure_backup_dir,
    format_size,
    get_backups,
    gzip_decompress_to_temp_file,
    mask_password,
    open_backup_temp_file,
    parse_backup_source_database,
    publish_backup,
    rotate_backups,
    run_postgres_via_docker_or_host,
    run_streaming_command,
    verify_checksum,
    warn_if_checksum_missing,
    write_checksum,
)

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX file mode bits only")


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


def test_rotate_backups_removes_zero_byte_files_before_counting_retention(tmp_path):
    old = tmp_path / "db_20260101_000000.sql.gz"
    middle = tmp_path / "db_20260102_000000.sql.gz"
    new = tmp_path / "db_20260103_000000.sql.gz"
    empty = tmp_path / "db_20260104_000000.sql.gz"
    _touch(old, 1)
    _touch(middle, 2)
    _touch(new, 3)
    empty.touch()

    removed = rotate_backups(tmp_path, "db_*.sql.gz", max_keep=2)

    assert removed == [empty, old]
    assert not old.exists()
    assert not empty.exists()
    assert middle.exists()
    assert new.exists()


def test_cleanup_incomplete_backups_removes_partial_artifacts(tmp_path):
    final = tmp_path / "db_20260101_000000.sql.gz"
    partial = tmp_path / "db_20260102_000000.sql.gz.partial"
    _touch(final, 1)
    _touch(partial, 2)

    removed = cleanup_incomplete_backups(tmp_path, "db_*.sql.gz")

    assert removed == [partial]
    assert final.exists()
    assert not partial.exists()


def test_cleanup_incomplete_backups_preserves_recent_partial_artifacts(tmp_path):
    recent_partial = tmp_path / "db_20260101_000000.sql.gz.partial"
    stale_partial = tmp_path / "db_20260102_000000.sql.gz.partial"
    _touch(recent_partial, time.time())
    _touch(stale_partial, time.time() - _backup_utils.STALE_PARTIAL_BACKUP_AGE_SECONDS - 1)

    removed = cleanup_incomplete_backups(tmp_path, "db_*.sql.gz")

    assert removed == [stale_partial]
    assert recent_partial.exists()
    assert not stale_partial.exists()


def test_backup_name_pattern_does_not_match_database_with_shared_prefix():
    pattern = backup_name_pattern("repom", ".sql.gz")

    assert pattern.fullmatch("repom_20260101_000000.sql.gz")
    assert not pattern.fullmatch("repom_dev_20260101_000000.sql.gz")


def test_rotate_backups_with_name_pattern_ignores_other_database_prefix_matches(tmp_path):
    prod_old = tmp_path / "repom_20260101_000000.sql.gz"
    prod_middle = tmp_path / "repom_20260102_000000.sql.gz"
    prod_new = tmp_path / "repom_20260103_000000.sql.gz"
    dev = tmp_path / "repom_dev_20260104_000000.sql.gz"
    _touch(prod_old, 1)
    _touch(prod_middle, 2)
    _touch(prod_new, 3)
    _touch(dev, 4)

    # A plain glob for "repom" also matches "repom_dev_...", since "*" swallows
    # "dev_20260104_000000"; name_pattern must keep rotation scoped to "repom".
    removed = rotate_backups(
        tmp_path, "repom_*.sql.gz", max_keep=2, name_pattern=backup_name_pattern("repom", ".sql.gz")
    )

    assert removed == [prod_old]
    assert not prod_old.exists()
    assert prod_middle.exists()
    assert prod_new.exists()
    assert dev.exists()


def test_cleanup_incomplete_backups_with_name_pattern_ignores_other_database(tmp_path):
    prod_empty = tmp_path / "repom_20260101_000000.sql.gz"
    dev_empty = tmp_path / "repom_dev_20260101_000000.sql.gz"
    prod_empty.touch()
    dev_empty.touch()

    removed = cleanup_incomplete_backups(
        tmp_path, "repom_*.sql.gz", name_pattern=backup_name_pattern("repom", ".sql.gz")
    )

    assert removed == [prod_empty]
    assert not prod_empty.exists()
    assert dev_empty.exists()


def test_parse_backup_source_database_matches_postgres_name():
    assert parse_backup_source_database("repom_dev_20260101_000000.sql.gz", ".sql.gz") == "repom_dev"


def test_parse_backup_source_database_matches_sqlite_name():
    assert parse_backup_source_database("repom_20260101_000000.sqlite3", ".sqlite3") == "repom"


def test_parse_backup_source_database_returns_none_for_legacy_postgres_name():
    assert parse_backup_source_database("db_20260101_000000.sql.gz", ".sql.gz") is None


def test_parse_backup_source_database_returns_none_for_unrelated_name():
    assert parse_backup_source_database("notes.txt", ".sql.gz") is None


def test_get_backups_lists_legacy_and_current_named_postgres_backups(tmp_path):
    legacy = tmp_path / "db_20260101_000000.sql.gz"
    current = tmp_path / "repom_20260102_000000.sql.gz"
    _touch(legacy, 1)
    _touch(current, 2)

    assert get_backups(tmp_path, "postgres") == [current, legacy]


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
        _backup_utils,
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
        _backup_utils,
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
        _backup_utils,
        "is_container_running",
        MagicMock(side_effect=DockerUnavailableError("docker command not found")),
    )

    result = run_postgres_via_docker_or_host(
        via_docker=via_docker,
        via_host=via_host,
        operation="backup",
    )

    assert result == "host-result"
    via_docker.assert_not_called()
    via_host.assert_called_once_with()


def test_run_postgres_via_docker_or_host_uses_host_when_docker_daemon_unavailable(
    monkeypatch, caplog
):
    """`docker ps` succeeds in finding the CLI but fails to reach the daemon
    (e.g. Docker Desktop installed but not running); the operation should
    fall back to host tools, with the daemon's stderr in the warning."""
    via_docker = MagicMock()
    via_host = MagicMock(return_value="host-result")

    monkeypatch.setattr(
        DockerCommandExecutor,
        "is_container_running",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                1,
                ["docker", "ps"],
                stderr="Cannot connect to the Docker daemon",
            )
        ),
    )

    with caplog.at_level("WARNING"):
        result = run_postgres_via_docker_or_host(
            via_docker=via_docker,
            via_host=via_host,
            operation="backup",
        )

    assert result == "host-result"
    via_docker.assert_not_called()
    via_host.assert_called_once_with()
    assert "Cannot connect to the Docker daemon" in caplog.text


def test_run_postgres_via_docker_or_host_accepts_explicit_container_name(monkeypatch):
    is_running = MagicMock(return_value=True)
    monkeypatch.setattr(_backup_utils, "is_container_running", is_running)

    result = run_postgres_via_docker_or_host(
        via_docker=lambda: "docker-result",
        via_host=lambda: "host-result",
        operation="backup",
        container_name="custom-postgres",
    )

    assert result == "docker-result"
    is_running.assert_called_once_with("custom-postgres")


@POSIX_ONLY
def test_ensure_backup_dir_creates_with_mode_0700(tmp_path):
    backup_dir = tmp_path / "backups"

    result = ensure_backup_dir(backup_dir)

    assert result == backup_dir
    assert backup_dir.is_dir()
    assert backup_dir.stat().st_mode & 0o777 == 0o700


@POSIX_ONLY
def test_ensure_backup_dir_tightens_existing_permissive_directory(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(mode=0o755)
    os.chmod(backup_dir, 0o755)

    ensure_backup_dir(backup_dir)

    assert backup_dir.stat().st_mode & 0o777 == 0o700


@POSIX_ONLY
def test_open_backup_temp_file_creates_with_mode_0600(tmp_path):
    target = tmp_path / "db_20260101_000000.sql.gz.partial"

    with open_backup_temp_file(target) as f:
        assert target.stat().st_mode & 0o777 == 0o600
        f.write(b"payload")

    assert target.read_bytes() == b"payload"


def test_open_backup_temp_file_refuses_to_reuse_existing_file(tmp_path):
    target = tmp_path / "db_20260101_000000.sql.gz.partial"
    target.write_bytes(b"stale")

    with pytest.raises(FileExistsError):
        open_backup_temp_file(target)


def test_write_checksum_and_verify_checksum_round_trip(tmp_path):
    backup_path = tmp_path / "db_20260101_000000.sql.gz"
    backup_path.write_bytes(b"backup payload")

    sidecar = write_checksum(backup_path)

    assert sidecar == checksum_path(backup_path)
    assert sidecar.exists()
    assert compute_checksum(backup_path) in sidecar.read_text(encoding="utf-8")
    assert verify_checksum(backup_path) is True


def test_verify_checksum_returns_false_when_no_sidecar_exists(tmp_path):
    backup_path = tmp_path / "db_20260101_000000.sql.gz"
    backup_path.write_bytes(b"backup payload")

    assert verify_checksum(backup_path) is False


def test_verify_checksum_raises_on_mismatch(tmp_path):
    backup_path = tmp_path / "db_20260101_000000.sql.gz"
    backup_path.write_bytes(b"backup payload")
    write_checksum(backup_path)

    backup_path.write_bytes(b"tampered payload")

    with pytest.raises(ChecksumError):
        verify_checksum(backup_path)


def test_rotate_backups_removes_checksum_sidecar_for_rotated_file(tmp_path):
    old = tmp_path / "db_20260101_000000.sql.gz"
    new = tmp_path / "db_20260102_000000.sql.gz"
    _touch(old, 1)
    _touch(new, 2)
    write_checksum(old)
    write_checksum(new)

    removed = rotate_backups(tmp_path, "db_*.sql.gz", max_keep=1)

    assert removed == [old]
    assert not checksum_path(old).exists()
    assert checksum_path(new).exists()


def test_cleanup_incomplete_backups_removes_checksum_sidecar_for_zero_byte_file(tmp_path):
    empty = tmp_path / "db_20260101_000000.sql.gz"
    empty.touch()
    checksum_path(empty).write_text("deadbeef  db_20260101_000000.sql.gz\n", encoding="utf-8")

    removed = cleanup_incomplete_backups(tmp_path, "db_*.sql.gz")

    assert removed == [empty]
    assert not checksum_path(empty).exists()


def test_build_pg_client_command_builds_host_argv():
    command = build_pg_client_command(
        "pg_dump",
        host="localhost",
        port=5432,
        user="postgres",
        database="repom_test",
        extra_args=["--clean", "--if-exists"],
    )

    assert command == [
        "pg_dump",
        "-h", "localhost",
        "-p", "5432",
        "-U", "postgres",
        "-d", "repom_test",
        "--clean",
        "--if-exists",
    ]


def test_build_pg_client_command_builds_docker_argv_without_host_flags():
    command = build_pg_client_command(
        "pg_dump",
        host="localhost",
        port=5432,
        user="postgres",
        database="repom_test",
        extra_args=["--clean"],
        container_name="repom-postgres",
    )

    assert command == [
        "docker", "exec", "repom-postgres",
        "pg_dump",
        "-U", "postgres",
        "-d", "repom_test",
        "--clean",
    ]


def test_build_pg_client_command_docker_stdin_adds_interactive_flag():
    command = build_pg_client_command(
        "psql",
        host="localhost",
        port=5432,
        user="postgres",
        database="repom_test",
        extra_args=["-v", "ON_ERROR_STOP=1"],
        container_name="repom-postgres",
        stdin=True,
    )

    assert command[:4] == ["docker", "exec", "-i", "repom-postgres"]


def test_build_pg_client_command_host_ignores_stdin_flag():
    command = build_pg_client_command(
        "psql",
        host="localhost",
        port=5432,
        user="postgres",
        database="repom_test",
        stdin=True,
    )

    assert "-i" not in command


def test_mask_password_replaces_password_in_text():
    assert mask_password("connection failed: secret", "secret") == "connection failed: ***"


def test_mask_password_is_noop_without_password():
    assert mask_password("connection failed", None) == "connection failed"
    assert mask_password("connection failed", "") == "connection failed"


def test_byte_counting_writer_counts_and_forwards_writes():
    sink = io.BytesIO()
    writer = ByteCountingWriter(sink)

    writer.write(b"hello")
    writer.write(b" world")

    assert writer.bytes_written == len(b"hello world")
    assert sink.getvalue() == b"hello world"


class TestRunStreamingCommand:
    """Exercises real child processes so the stdin/stdout streaming and the
    background stderr-draining thread run for real (repom#167: a child
    writing more to stderr than an OS pipe buffer holds must never deadlock
    the caller)."""

    def test_streams_large_stdout_and_drains_large_stderr_without_deadlock(self, monkeypatch):
        monkeypatch.setenv("FAKE_CHILD_STDOUT_BYTES", str(1024 * 1024))
        monkeypatch.setenv("FAKE_CHILD_STDERR_BYTES", str(1024 * 1024))
        sink = io.BytesIO()

        result = run_streaming_command(fake_client_command(), stdout_file=sink)

        assert result.returncode == 0
        assert len(sink.getvalue()) == 1024 * 1024
        assert len(result.stderr.encode("utf-8", errors="replace")) == 1024 * 1024

    def test_streams_large_stdin_and_drains_large_stderr_without_deadlock(self, monkeypatch, tmp_path):
        sink_path = tmp_path / "stdin_echo.bin"
        monkeypatch.setenv("FAKE_CHILD_STDIN_SINK", str(sink_path))
        monkeypatch.setenv("FAKE_CHILD_STDERR_BYTES", str(1024 * 1024))
        payload = b"S" * (1024 * 1024)

        result = run_streaming_command(fake_client_command(), stdin_file=io.BytesIO(payload))

        assert result.returncode == 0
        assert sink_path.read_bytes() == payload

    def test_delivers_exact_stdin_bytes_without_corruption(self, monkeypatch, tmp_path):
        sink_path = tmp_path / "stdin_echo.bin"
        monkeypatch.setenv("FAKE_CHILD_STDIN_SINK", str(sink_path))
        payload = os.urandom(2048)

        result = run_streaming_command(fake_client_command(), stdin_file=io.BytesIO(payload))

        assert result.returncode == 0
        assert sink_path.read_bytes() == payload

    def test_reports_nonzero_exit_code(self, monkeypatch):
        monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "1")

        result = run_streaming_command(fake_client_command(), stdout_file=io.BytesIO())

        assert result.returncode == 1

    def test_masks_password_in_returned_stderr(self, monkeypatch):
        monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "connection failed: secret\n")

        result = run_streaming_command(
            fake_client_command(), stdout_file=io.BytesIO(), password="secret"
        )

        assert "secret" not in result.stderr
        assert "***" in result.stderr

    def test_raises_file_not_found_for_missing_binary(self):
        with pytest.raises(FileNotFoundError):
            run_streaming_command(missing_binary_command(), stdout_file=io.BytesIO())

    def test_returns_child_error_when_child_exits_before_reading_all_stdin(self, monkeypatch):
        """A child (standing in for psql/pg_restore) that stops reading stdin
        and exits with an error while a large payload is still being written
        must report its real exit code and stderr, not a raised
        BrokenPipeError (repom#167 review round 2)."""
        monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "3")
        monkeypatch.setenv("FAKE_CHILD_STDERR_TEXT", "ERROR: relation does not exist\n")
        payload = b"S" * (20 * 1024 * 1024)

        result = run_streaming_command(fake_client_command(), stdin_file=io.BytesIO(payload))

        assert result.returncode == 3
        assert "relation does not exist" in result.stderr

    def test_reports_failure_when_child_exits_zero_without_reading_all_stdin(self, monkeypatch):
        """If the stdin copy is cut short but the child still exits 0, that
        must be reported as a failure rather than silently returning
        success for a restore that was not fully applied."""
        monkeypatch.setenv("FAKE_CHILD_EXIT_CODE", "0")
        payload = b"S" * (20 * 1024 * 1024)

        result = run_streaming_command(fake_client_command(), stdin_file=io.BytesIO(payload))

        assert result.returncode != 0


class TestGzipDecompressToTempFile:
    def test_decompresses_full_content_into_sibling_temp_file(self, tmp_path):
        source = tmp_path / "backup.sql.gz"
        with gzip.open(source, "wb") as f:
            f.write(b"SELECT 1;" * 1000)

        temp_path = gzip_decompress_to_temp_file(source)
        try:
            assert temp_path.parent == source.parent
            assert temp_path.read_bytes() == b"SELECT 1;" * 1000
        finally:
            temp_path.unlink(missing_ok=True)

    @POSIX_ONLY
    def test_temp_file_is_0600(self, tmp_path):
        source = tmp_path / "backup.sql.gz"
        with gzip.open(source, "wb") as f:
            f.write(b"payload")

        temp_path = gzip_decompress_to_temp_file(source)
        try:
            assert temp_path.stat().st_mode & 0o777 == 0o600
        finally:
            temp_path.unlink(missing_ok=True)

    def test_truncated_archive_raises_before_leaving_a_temp_file(self, tmp_path):
        source = tmp_path / "backup.sql.gz"
        with gzip.open(source, "wb") as f:
            f.write(b"SELECT 1;" * 1000)
        truncated = source.read_bytes()[:-10]
        source.write_bytes(truncated)

        with pytest.raises(EOFError):
            gzip_decompress_to_temp_file(source)

        assert list(tmp_path.glob("*.decompressed")) == []

    def test_non_gzip_file_raises_bad_gzip_file(self, tmp_path):
        source = tmp_path / "backup.sql.gz"
        source.write_bytes(b"not a gzip file")

        with pytest.raises(gzip.BadGzipFile):
            gzip_decompress_to_temp_file(source)

        assert list(tmp_path.glob("*.decompressed")) == []


class TestWarnIfChecksumMissing:
    def test_missing_checksum_warns_and_does_not_raise(self, tmp_path, capsys):
        backup_file = tmp_path / "db_20260101_000000.sql.gz"
        backup_file.write_bytes(b"payload")

        warn_if_checksum_missing(backup_file)

        assert "no checksum recorded" in capsys.readouterr().out.lower()

    def test_matching_checksum_does_not_warn(self, tmp_path, capsys):
        backup_file = tmp_path / "db_20260101_000000.sql.gz"
        backup_file.write_bytes(b"payload")
        write_checksum(backup_file)

        warn_if_checksum_missing(backup_file)

        assert "no checksum recorded" not in capsys.readouterr().out.lower()

    def test_mismatched_checksum_raises(self, tmp_path):
        backup_file = tmp_path / "db_20260101_000000.sql.gz"
        backup_file.write_bytes(b"payload")
        write_checksum(backup_file)
        backup_file.write_bytes(b"tampered")

        with pytest.raises(ChecksumError):
            warn_if_checksum_missing(backup_file)


class TestPublishBackup:
    def test_raises_and_removes_partial_when_empty(self, tmp_path):
        partial_path = tmp_path / "repom_20260101_000000.sql.gz.partial"
        partial_path.write_bytes(b"\x1f\x8b")  # gzip header only, no payload
        backup_path = tmp_path / "repom_20260101_000000.sql.gz"

        with pytest.raises(BackupError, match="empty"):
            publish_backup(
                partial_path,
                backup_path,
                tmp_path,
                "repom_*.sql.gz",
                3,
                empty=True,
                empty_message="pg_dump produced an empty backup",
            )

        assert not partial_path.exists()
        assert not backup_path.exists()

    def test_publishes_checksums_and_rotates_when_not_empty(self, tmp_path):
        old = tmp_path / "repom_20260101_000000.sql.gz"
        old.write_bytes(b"old payload")
        os.utime(old, (1, 1))
        write_checksum(old)

        partial_path = tmp_path / "repom_20260102_000000.sql.gz.partial"
        partial_path.write_bytes(b"new payload")
        backup_path = tmp_path / "repom_20260102_000000.sql.gz"

        publish_backup(
            partial_path,
            backup_path,
            tmp_path,
            "repom_*.sql.gz",
            1,
            empty=False,
            empty_message="unused",
        )

        assert not partial_path.exists()
        assert backup_path.read_bytes() == b"new payload"
        assert checksum_path(backup_path).exists()
        assert not old.exists()
        assert not checksum_path(old).exists()
