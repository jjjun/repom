"""Confirmation-guard tests for the alembic_reset console script (repom#135).

See tests/unit_tests/test_alembic_reset.py for AlembicReset class behavior;
these tests only cover the script's confirmation guard and alembic.ini
resolution (repom#160).
"""

from tests._init import *

import sys
from io import BytesIO, StringIO, TextIOWrapper
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect, text

from repom.alembic import AlembicTemplates
from repom.scripts import alembic_reset


def _mock_config(
    exec_env="dev",
    db_url="sqlite:///data/repom_dev.sqlite3",
    root_path="/tmp/repom"
):
    config = MagicMock()
    config.exec_env = exec_env
    config.db_url = db_url
    config.root_path = root_path
    return config


def _write_default_ini(root_path):
    """Write the standard alembic.ini (script_location + alembic/versions)."""
    ini_path = root_path / "alembic.ini"
    ini_path.write_text(AlembicTemplates.generate_alembic_ini(
        script_location="alembic",
        version_locations="%(here)s/alembic/versions",
    ))
    return ini_path


def test_alembic_reset_requires_confirmation(monkeypatch, tmp_path):
    _write_default_ini(tmp_path)
    monkeypatch.setattr(alembic_reset, "config", _mock_config(root_path=str(tmp_path)))
    monkeypatch.setattr(sys, "argv", ["alembic_reset"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    with pytest.raises(SystemExit) as exc_info:
        alembic_reset.main()

    assert exc_info.value.code != 0
    setup_cls.from_ini.return_value.reset_migrations.assert_not_called()


def test_alembic_reset_refuses_prod_env(monkeypatch, tmp_path):
    _write_default_ini(tmp_path)
    monkeypatch.setattr(
        alembic_reset,
        "config",
        _mock_config(exec_env="prod", root_path=str(tmp_path))
    )
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    with pytest.raises(SystemExit) as exc_info:
        alembic_reset.main()

    assert exc_info.value.code != 0
    setup_cls.from_ini.return_value.reset_migrations.assert_not_called()


def test_alembic_reset_proceeds_with_yes_flag_on_non_tty(monkeypatch, tmp_path):
    _write_default_ini(tmp_path)
    monkeypatch.setattr(alembic_reset, "config", _mock_config(root_path=str(tmp_path)))
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    alembic_reset.main()

    setup_cls.from_ini.return_value.reset_migrations.assert_called_once()


def test_alembic_reset_requires_ini_file(monkeypatch, tmp_path):
    """repom#160: fail with a clear error instead of falling back to
    AlembicSetup's built-in defaults when the ini file is missing.
    """
    monkeypatch.setattr(alembic_reset, "config", _mock_config(root_path=str(tmp_path)))
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    with pytest.raises(SystemExit) as exc_info:
        alembic_reset.main()

    assert exc_info.value.code != 0
    setup_cls.from_ini.assert_not_called()


def test_alembic_reset_completes_with_cp932_stdout(monkeypatch, tmp_path):
    """repom#152: a destructive reset must finish even when stdout can't
    encode the check-mark/cross symbols the script used to print - those
    now use the ASCII [OK]/[NG] markers instead.
    """
    db_path = tmp_path / "reset.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))

    versions_dir = tmp_path / "alembic" / "versions"
    versions_dir.mkdir(parents=True)
    (versions_dir / "0001_test.py").write_text("# migration")
    (versions_dir / "__pycache__").mkdir()

    _write_default_ini(tmp_path)

    config = _mock_config(db_url=db_url, root_path=str(tmp_path))
    monkeypatch.setattr(alembic_reset, "config", config)
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    cp932_stdout = TextIOWrapper(BytesIO(), encoding="cp932")
    monkeypatch.setattr(sys, "stdout", cp932_stdout)

    alembic_reset.main()

    cp932_stdout.flush()
    output = cp932_stdout.buffer.getvalue().decode("cp932")

    assert "[OK] Alembic migrations reset successfully" in output
    assert not inspect(engine).has_table("alembic_version")
    assert not (versions_dir / "0001_test.py").exists()
    assert not (versions_dir / "__pycache__").exists()


def test_alembic_reset_default_layout_behaves_as_today(monkeypatch, tmp_path, capsys):
    """repom#160 acceptance: an ini with only the generated defaults resets
    the same alembic_version table and alembic/versions directory as before.
    """
    db_path = tmp_path / "default.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))

    versions_dir = tmp_path / "alembic" / "versions"
    versions_dir.mkdir(parents=True)
    (versions_dir / "__init__.py").touch()
    (versions_dir / "0001_test.py").write_text("# migration")

    _write_default_ini(tmp_path)

    monkeypatch.setattr(
        alembic_reset, "config", _mock_config(db_url=db_url, root_path=str(tmp_path))
    )
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    alembic_reset.main()

    output = capsys.readouterr().out
    assert "version table: alembic_version" in output
    assert str(versions_dir) in output
    assert not inspect(engine).has_table("alembic_version")
    assert not (versions_dir / "0001_test.py").exists()
    assert (versions_dir / "__init__.py").exists()


def test_alembic_reset_scoped_to_ini_namespace(monkeypatch, tmp_path, capsys):
    """repom#160 acceptance: --config selects an independent migration
    namespace, leaving the default alembic_version table/directory alone.
    """
    db_path = tmp_path / "ns2.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE alembic_version_ns2 (version_num VARCHAR(32))"
        ))
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32))"
        ))

    ns2_versions = tmp_path / "migrations_ns2"
    ns2_versions.mkdir()
    (ns2_versions / "__init__.py").touch()
    (ns2_versions / "0001_ns2.py").write_text("# ns2 migration")

    default_versions = tmp_path / "alembic" / "versions"
    default_versions.mkdir(parents=True)
    (default_versions / "__init__.py").touch()
    (default_versions / "0001_default.py").write_text("# default migration")

    ini_path = tmp_path / "alembic_ns2.ini"
    ini_path.write_text(AlembicTemplates.generate_alembic_ini(
        script_location="alembic",
        version_locations="%(here)s/migrations_ns2",
        version_table="alembic_version_ns2",
    ))

    monkeypatch.setattr(
        alembic_reset, "config", _mock_config(db_url=db_url, root_path=str(tmp_path))
    )
    monkeypatch.setattr(
        sys, "argv", ["alembic_reset", "--yes", "-c", str(ini_path)]
    )
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    alembic_reset.main()

    output = capsys.readouterr().out
    assert "version table: alembic_version_ns2" in output
    assert str(ns2_versions) in output

    assert not inspect(engine).has_table("alembic_version_ns2")
    assert inspect(engine).has_table("alembic_version")

    assert not (ns2_versions / "0001_ns2.py").exists()
    assert (ns2_versions / "__init__.py").exists()
    assert (default_versions / "0001_default.py").exists()
    assert (default_versions / "__init__.py").exists()
