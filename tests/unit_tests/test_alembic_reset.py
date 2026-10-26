"""Unit tests for Alembic migration reset functionality."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql

from repom.alembic import AlembicReset
from repom.config import config
from repom.exceptions import UnsafeVersionsDirectoryError
import repom.alembic.reset as reset_module


def test_drop_alembic_version_table_uses_default_name(tmp_path):
    db_path = tmp_path / "default.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32))"
        ))

    reset = AlembicReset(db_url, tmp_path)
    reset.drop_alembic_version_table()

    assert not inspect(engine).has_table("alembic_version")


def test_drop_alembic_version_table_uses_custom_name_on_sqlite(tmp_path):
    db_path = tmp_path / "custom.db"
    db_url = f"sqlite:///{db_path}"
    version_table = "alembic-version-app2"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            'CREATE TABLE "alembic-version-app2" (version_num VARCHAR(32))'
        ))

    reset = AlembicReset(
        db_url,
        tmp_path,
        version_table=version_table
    )
    reset.drop_alembic_version_table()

    assert not inspect(engine).has_table(version_table)


def test_drop_alembic_version_table_ignores_schema_on_sqlite(tmp_path):
    db_path = tmp_path / "schema.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32))"
        ))

    reset = AlembicReset(
        db_url,
        tmp_path,
        version_table_schema="migration_ns"
    )
    reset.drop_alembic_version_table()

    assert not inspect(engine).has_table("alembic_version")


def test_drop_alembic_version_table_uses_custom_name_on_postgresql(tmp_path):
    engine = MagicMock()
    engine.dialect = postgresql.dialect()
    conn = engine.connect.return_value.__enter__.return_value

    inspector = MagicMock()
    inspector.has_table.return_value = True

    with (
        patch("repom.alembic.reset.create_engine", return_value=engine),
        patch("repom.alembic.reset.inspect", return_value=inspector),
    ):
        reset = AlembicReset(
            "postgresql://localhost/test",
            tmp_path,
            version_table="alembic-version-app2"
        )
        reset.drop_alembic_version_table()

    inspector.has_table.assert_called_once_with(
        "alembic-version-app2", schema=None
    )
    (drop_call,) = conn.execute.call_args_list
    assert str(drop_call.args[0]) == 'DROP TABLE "alembic-version-app2"'
    conn.commit.assert_called_once_with()
    engine.dispose.assert_called_once_with()


def test_drop_alembic_version_table_uses_custom_schema_on_postgresql(tmp_path):
    engine = MagicMock()
    engine.dialect = postgresql.dialect()
    conn = engine.connect.return_value.__enter__.return_value

    inspector = MagicMock()
    inspector.has_table.return_value = True

    with (
        patch("repom.alembic.reset.create_engine", return_value=engine),
        patch("repom.alembic.reset.inspect", return_value=inspector),
    ):
        reset = AlembicReset(
            "postgresql://localhost/test",
            tmp_path,
            version_table_schema="migration-fast-domain"
        )
        reset.drop_alembic_version_table()

    inspector.has_table.assert_called_once_with(
        "alembic_version", schema="migration-fast-domain"
    )
    (drop_call,) = conn.execute.call_args_list
    assert str(drop_call.args[0]) == (
        'DROP TABLE "migration-fast-domain".alembic_version'
    )
    conn.commit.assert_called_once_with()
    engine.dispose.assert_called_once_with()


def test_drop_alembic_version_table_names_absent_table(tmp_path, capsys):
    db_url = f"sqlite:///{tmp_path / 'absent.db'}"
    reset = AlembicReset(
        db_url,
        tmp_path,
        version_table="alembic_version_app2"
    )

    reset.drop_alembic_version_table()

    assert capsys.readouterr().out == (
        "[OK] alembic_version_app2 table does not exist\n"
    )


def test_drop_alembic_version_table_disposes_engine(monkeypatch, tmp_path):
    """repom#160: an undisposed engine keeps a pooled connection open, which
    leaves a file-based SQLite database locked on Windows until GC'd.
    """
    db_path = tmp_path / "dispose.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32))"
        ))
    engine.dispose()

    reset = AlembicReset(db_url, tmp_path)
    dispose = MagicMock(wraps=engine.dispose)
    monkeypatch.setattr(reset_module, "create_engine", lambda _: engine)
    monkeypatch.setattr(engine, "dispose", dispose)
    reset.drop_alembic_version_table()

    dispose.assert_called_once_with()


def test_delete_migration_files_defaults_to_versions_dir(tmp_path):
    (tmp_path / "__init__.py").touch()
    (tmp_path / "0001_test.py").write_text("# migration")

    reset = AlembicReset("sqlite:///unused.db", tmp_path)
    reset.delete_migration_files()

    assert not (tmp_path / "0001_test.py").exists()
    assert (tmp_path / "__init__.py").exists()


def test_delete_migration_files_accepts_override_directory(tmp_path):
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    (other_dir / "__init__.py").touch()
    (other_dir / "0001_other.py").write_text("# migration")

    reset = AlembicReset("sqlite:///unused.db", tmp_path)
    reset.delete_migration_files(other_dir)

    assert not (other_dir / "0001_other.py").exists()
    assert (other_dir / "__init__.py").exists()


def _link_or_skip(link, target):
    """Create a directory symlink, or a junction on Windows without the
    symlink privilege; skip when neither is available."""
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
        )
        if result.returncode == 0:
            return
    pytest.skip("directory links are not available")


def test_delete_migration_files_refuses_project_dir(tmp_path):
    """repom#274: a versions dir equal to the ini directory would delete the
    project's own top-level *.py files."""
    (tmp_path / "app.py").write_text("# project code")

    reset = AlembicReset(
        "sqlite:///unused.db", tmp_path, project_dirs=[tmp_path]
    )

    with pytest.raises(UnsafeVersionsDirectoryError):
        reset.delete_migration_files()

    assert (tmp_path / "app.py").exists()


def test_delete_migration_files_refuses_project_dir_via_dot_segments(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "app.py").write_text("# project code")

    reset = AlembicReset(
        "sqlite:///unused.db", nested / "..", project_dirs=[tmp_path]
    )

    with pytest.raises(UnsafeVersionsDirectoryError):
        reset.delete_migration_files()

    assert (tmp_path / "app.py").exists()


def test_delete_migration_files_refuses_config_root_path(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "root_path", str(tmp_path))
    (tmp_path / "app.py").write_text("# project code")

    reset = AlembicReset("sqlite:///unused.db", tmp_path)

    with pytest.raises(UnsafeVersionsDirectoryError):
        reset.delete_migration_files()

    assert (tmp_path / "app.py").exists()


def test_delete_migration_files_refuses_current_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("# project code")

    reset = AlembicReset("sqlite:///unused.db", tmp_path)

    with pytest.raises(UnsafeVersionsDirectoryError):
        reset.delete_migration_files()

    assert (tmp_path / "app.py").exists()


def test_delete_migration_files_allow_project_root_opt_in(tmp_path):
    (tmp_path / "0001_test.py").write_text("# migration")

    reset = AlembicReset(
        "sqlite:///unused.db",
        tmp_path,
        project_dirs=[tmp_path],
        allow_project_root=True,
    )
    reset.delete_migration_files()

    assert not (tmp_path / "0001_test.py").exists()


def test_delete_migration_files_refuses_symlinked_versions_dir(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "0001_test.py").write_text("# migration")
    link = tmp_path / "versions"
    _link_or_skip(link, target)

    reset = AlembicReset("sqlite:///unused.db", link)

    with pytest.raises(UnsafeVersionsDirectoryError):
        reset.delete_migration_files()

    assert (target / "0001_test.py").exists()


def test_delete_migration_files_refuses_symlinked_versions_dir_with_opt_in(
    tmp_path
):
    target = tmp_path / "target"
    target.mkdir()
    (target / "0001_test.py").write_text("# migration")
    link = tmp_path / "versions"
    _link_or_skip(link, target)

    reset = AlembicReset("sqlite:///unused.db", link, allow_project_root=True)

    with pytest.raises(UnsafeVersionsDirectoryError):
        reset.delete_migration_files()

    assert (target / "0001_test.py").exists()


def test_delete_migration_files_does_not_follow_symlinked_pycache(
    tmp_path, capsys
):
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()
    (versions_dir / "0001_test.py").write_text("# migration")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.pyc").write_text("keep")
    _link_or_skip(versions_dir / "__pycache__", outside)

    reset = AlembicReset("sqlite:///unused.db", versions_dir)
    reset.delete_migration_files()

    assert not (versions_dir / "0001_test.py").exists()
    assert (outside / "keep.pyc").exists()
    assert (versions_dir / "__pycache__").exists()
    assert "Skipped linked __pycache__" in capsys.readouterr().out
