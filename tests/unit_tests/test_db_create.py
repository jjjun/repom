"""Strict model-import guard tests for the db_create console script (repom#138)."""

from tests._init import *

from unittest.mock import MagicMock

import pytest
from basekit.discovery import DiscoveryError, DiscoveryFailure

from repom.scripts import db_create


def test_db_create_calls_load_models_with_strict_true(monkeypatch):
    """create_all against a partial Base.metadata silently skips creating
    whichever tables failed to import, so db_create must force strict import
    checking even when a project has opted model_import_strict out.
    """
    fake_config = MagicMock()
    fake_config.db_type = 'sqlite'
    fake_config.model_import_strict = False
    monkeypatch.setattr(db_create, "config", fake_config)

    fake_load_models = MagicMock(return_value=[])
    monkeypatch.setattr(db_create, "load_models", fake_load_models)

    fake_base = MagicMock()
    monkeypatch.setattr(db_create, "Base", fake_base)
    fake_engine = MagicMock()
    monkeypatch.setattr(db_create, "get_sync_engine", MagicMock(return_value=fake_engine))

    db_create.main()

    fake_load_models.assert_called_once_with(context="db_create", strict=True)
    fake_base.metadata.create_all.assert_called_once_with(bind=fake_engine)


def test_db_create_raises_on_import_failure(monkeypatch):
    """A model module that fails to import must abort before create_all runs,
    regardless of config.model_import_strict.
    """
    fake_config = MagicMock()
    fake_config.db_type = 'sqlite'
    fake_config.model_import_strict = False
    monkeypatch.setattr(db_create, "config", fake_config)

    failure = DiscoveryFailure(
        target="myapp.models.broken",
        target_type="module",
        exception_type="ImportError",
        message="cannot import name broken_dependency",
    )
    monkeypatch.setattr(
        db_create, "load_models", MagicMock(side_effect=DiscoveryError([failure]))
    )

    fake_base = MagicMock()
    monkeypatch.setattr(db_create, "Base", fake_base)
    monkeypatch.setattr(db_create, "get_sync_engine", MagicMock())

    with pytest.raises(DiscoveryError):
        db_create.main()

    fake_base.metadata.create_all.assert_not_called()
