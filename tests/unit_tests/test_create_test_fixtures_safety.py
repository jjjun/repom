"""Safety guard tests for create_test_fixtures (repom#135).

create_test_fixtures drops every table in Base.metadata when its
session-scoped engine fixture tears down. These tests verify the factory
refuses to target a non-test, non-in-memory database unless the caller opts
in explicitly.
"""

from tests._init import *

import pytest

from repom.config import config
from repom.testing import create_test_fixtures


def test_create_test_fixtures_refuses_non_test_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "exec_env", "dev")
    db_path = tmp_path / "repom_dev.sqlite3"
    db_url = f"sqlite:///{db_path}"

    with pytest.raises(RuntimeError):
        create_test_fixtures(db_url=db_url)

    assert not db_path.exists()


def test_create_test_fixtures_allows_in_memory_sqlite(monkeypatch):
    monkeypatch.setattr(config, "exec_env", "dev")

    db_engine, db_test = create_test_fixtures()

    assert callable(db_engine)
    assert callable(db_test)


def test_create_test_fixtures_requires_explicit_opt_in_for_real_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "exec_env", "dev")
    db_path = tmp_path / "repom_dev.sqlite3"
    db_url = f"sqlite:///{db_path}"

    with pytest.raises(RuntimeError):
        create_test_fixtures(db_url=db_url)

    db_engine, _ = create_test_fixtures(db_url=db_url, allow_destructive=True)
    engine_generator = db_engine.__wrapped__()
    next(engine_generator)
    try:
        assert db_path.exists()
    finally:
        next(engine_generator, None)
