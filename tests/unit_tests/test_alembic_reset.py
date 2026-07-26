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


def test_drop_alembic_version_table_uses_custom_name_on_postgresql(tmp_path):
    engine = MagicMock()
    engine.dialect = postgresql.dialect()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = (
        "alembic-version-app2",
    )

    with patch("repom.alembic.reset.create_engine", return_value=engine):
        reset = AlembicReset(
            "postgresql://localhost/test",
            tmp_path,
            version_table="alembic-version-app2"
        )
        reset.drop_alembic_version_table()

    existence_call, drop_call = conn.execute.call_args_list
    assert "table_name = :version_table" in str(existence_call.args[0])
    assert existence_call.args[1] == {
        "version_table": "alembic-version-app2"
    }
    assert str(drop_call.args[0]) == 'DROP TABLE "alembic-version-app2"'
    conn.commit.assert_called_once_with()


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
