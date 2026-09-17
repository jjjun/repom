"""Unit tests for Alembic migration reset functionality."""

from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql

from repom.alembic import AlembicReset


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


def test_drop_alembic_version_table_disposes_engine(tmp_path):
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
    reset.drop_alembic_version_table()

    db_path.unlink()


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
