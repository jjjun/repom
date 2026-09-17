"""Confirmation-guard tests for the alembic_reset console script (repom#135).

See tests/unit_tests/test_alembic_reset.py for AlembicReset class behavior;
these tests only cover the script's confirmation guard.
"""

from tests._init import *

import sys
from io import BytesIO, StringIO, TextIOWrapper
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect, text

from repom.scripts import alembic_reset


def _mock_config(exec_env="dev", db_url="sqlite:///data/repom_dev.sqlite3"):
    config = MagicMock()
    config.exec_env = exec_env
    config.db_url = db_url
    config.root_path = "/tmp/repom"
    return config


def test_alembic_reset_requires_confirmation(monkeypatch):
    monkeypatch.setattr(alembic_reset, "config", _mock_config())
    monkeypatch.setattr(sys, "argv", ["alembic_reset"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    with pytest.raises(SystemExit) as exc_info:
        alembic_reset.main()

    assert exc_info.value.code != 0
    setup_cls.return_value.reset_migrations.assert_not_called()


def test_alembic_reset_refuses_prod_env(monkeypatch):
    monkeypatch.setattr(alembic_reset, "config", _mock_config(exec_env="prod"))
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    with pytest.raises(SystemExit) as exc_info:
        alembic_reset.main()

    assert exc_info.value.code != 0
    setup_cls.return_value.reset_migrations.assert_not_called()


def test_alembic_reset_proceeds_with_yes_flag_on_non_tty(monkeypatch):
    monkeypatch.setattr(alembic_reset, "config", _mock_config())
    monkeypatch.setattr(sys, "argv", ["alembic_reset", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    setup_cls = MagicMock()
    monkeypatch.setattr(alembic_reset, "AlembicSetup", setup_cls)

    alembic_reset.main()

    setup_cls.return_value.reset_migrations.assert_called_once()


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

    config = _mock_config(db_url=db_url)
    config.root_path = str(tmp_path)
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
