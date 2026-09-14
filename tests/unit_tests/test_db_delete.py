"""Confirmation-guard tests for the db_delete console script (repom#135)."""

from tests._init import *

import sys
from io import StringIO
from unittest.mock import MagicMock

import pytest

from repom.scripts import db_delete


def _mock_config(exec_env="dev", db_url="sqlite:///data/repom_dev.sqlite3", db_type="sqlite"):
    config = MagicMock()
    config.exec_env = exec_env
    config.db_url = db_url
    config.db_type = db_type
    return config


def test_db_delete_requires_confirmation(monkeypatch):
    monkeypatch.setattr(db_delete, "config", _mock_config())
    monkeypatch.setattr(sys, "argv", ["db_delete"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    fake_base = MagicMock()
    monkeypatch.setattr(db_delete, "Base", fake_base)
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock())

    with pytest.raises(SystemExit) as exc_info:
        db_delete.main()

    assert exc_info.value.code != 0
    fake_base.metadata.drop_all.assert_not_called()


def test_db_delete_refuses_prod_env(monkeypatch):
    monkeypatch.setattr(db_delete, "config", _mock_config(exec_env="prod"))
    monkeypatch.setattr(sys, "argv", ["db_delete", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    fake_base = MagicMock()
    monkeypatch.setattr(db_delete, "Base", fake_base)
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock())

    with pytest.raises(SystemExit) as exc_info:
        db_delete.main()

    assert exc_info.value.code != 0
    fake_base.metadata.drop_all.assert_not_called()


def test_db_delete_proceeds_with_yes_flag_on_non_tty(monkeypatch):
    monkeypatch.setattr(db_delete, "config", _mock_config())
    monkeypatch.setattr(sys, "argv", ["db_delete", "--yes"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))
    fake_base = MagicMock()
    monkeypatch.setattr(db_delete, "Base", fake_base)
    monkeypatch.setattr(db_delete, "load_models", MagicMock())
    fake_engine = MagicMock()
    monkeypatch.setattr(db_delete, "get_sync_engine", MagicMock(return_value=fake_engine))

    db_delete.main()

    fake_base.metadata.drop_all.assert_called_once_with(bind=fake_engine)
