"""Confirmation-guard tests for the alembic_reset console script (repom#135).

See tests/unit_tests/test_alembic_reset.py for AlembicReset class behavior;
these tests only cover the script's confirmation guard.
"""

from tests._init import *

import sys
from io import StringIO
from unittest.mock import MagicMock

import pytest

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
