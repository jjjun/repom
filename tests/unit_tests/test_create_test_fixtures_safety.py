"""Safety guard tests for create_test_fixtures (repom#135).

create_test_fixtures drops every table in Base.metadata when its
session-scoped engine fixture tears down. These tests verify the factory
refuses to target a non-test, non-in-memory database unless the caller opts
in explicitly.
"""


import sqlite3

import pytest

from repom.config import config
from repom.testing import (
    _is_in_memory_sqlite_url,
    create_async_test_fixtures,
    create_test_fixtures,
)


@pytest.mark.parametrize("exec_env", ["TEST", " test ", "Test"])
@pytest.mark.parametrize(
    "create_fixtures", [create_test_fixtures, create_async_test_fixtures]
)
def test_fixture_factories_accept_normalized_test_exec_env(
    tmp_path, monkeypatch, exec_env, create_fixtures
):
    monkeypatch.setattr(config, "exec_env", exec_env)
    db_path = tmp_path / "repom_test.sqlite3"

    db_engine, db_test = create_fixtures(db_url=f"sqlite:///{db_path}")

    assert callable(db_engine)
    assert callable(db_test)
    assert not db_path.exists()


def test_create_async_test_fixtures_refuses_non_test_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "exec_env", "dev")
    db_path = tmp_path / "repom_dev.sqlite3"
    db_url = f"sqlite:///{db_path}"

    with pytest.raises(RuntimeError, match="Refusing to create test fixtures"):
        create_async_test_fixtures(db_url=db_url)

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


@pytest.mark.parametrize(
    ("create_fixtures", "driver"),
    [
        (create_test_fixtures, "sqlite"),
        (create_async_test_fixtures, "sqlite+aiosqlite"),
    ],
)
@pytest.mark.parametrize(
    "query",
    [
        "check_same_thread=:memory:",
        "check_same_thread=%3Amemory%3A",
        "check_same_thread=true&check_same_thread=:memory:",
    ],
)
def test_fixture_factories_reject_file_urls_with_memory_query_values(
    tmp_path, monkeypatch, create_fixtures, driver, query
):
    monkeypatch.setattr(config, "exec_env", "dev")
    db_path = tmp_path / "repom_dev.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")

    db_url = f"{driver}:///{db_path}?{query}"
    with pytest.raises(RuntimeError, match="Refusing to create test fixtures"):
        create_fixtures(db_url=db_url)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT value FROM sentinel").fetchone() == (
            "preserved",
        )


@pytest.mark.parametrize(
    ("create_fixtures", "driver"),
    [
        (create_test_fixtures, "sqlite"),
        (create_async_test_fixtures, "sqlite+aiosqlite"),
    ],
)
def test_fixture_factories_reject_memory_marker_in_sqlite_filename(
    monkeypatch, create_fixtures, driver
):
    monkeypatch.setattr(config, "exec_env", "dev")

    with pytest.raises(RuntimeError, match="Refusing to create test fixtures"):
        create_fixtures(db_url=f"{driver}:///repom:memory:.sqlite3")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite://", True),
        ("sqlite:///:memory:", True),
        ("sqlite:///:memory:?check_same_thread=false", False),
        ("sqlite://?check_same_thread=false", False),
        ("sqlite:///:memory:?uri=true&mode=rwc", False),
        ("sqlite+pysqlite:///:memory:", True),
        ("sqlite+aiosqlite:///:memory:", True),
        ("sqlite+aiosqlite:///file:memdb?mode=memory&uri=true", True),
        ("sqlite:///file:memdb?mode=memory&cache=shared&uri=true", True),
        ("sqlite:///file::memory:?cache=shared&uri=true", True),
        ("sqlite:///file:memdb?mode=memory&cache=shared", False),
        ("sqlite:///file:memdb?mode=memory&uri=false", False),
        ("sqlite:///file:memdb?mode=ro&uri=true", False),
        ("sqlite:///file:memdb?mode=memory&mode=ro&uri=true", False),
        ("sqlite:///file:memdb?mode=memory&cache=invalid&uri=true", False),
        ("sqlite:///repom:memory:.sqlite3", False),
        ("sqlite:///repom.sqlite3?check_same_thread=:memory:", False),
        ("sqlite://[::1", False),
    ],
)
def test_in_memory_sqlite_url_classifier_requires_unambiguous_memory_target(
    url, expected
):
    assert _is_in_memory_sqlite_url(url) is expected


@pytest.mark.parametrize(
    ("create_fixtures", "driver"),
    [
        (create_test_fixtures, "sqlite"),
        (create_async_test_fixtures, "sqlite+aiosqlite"),
    ],
)
def test_fixture_factories_allow_explicit_destructive_opt_in_for_file_database(
    tmp_path, monkeypatch, create_fixtures, driver
):
    monkeypatch.setattr(config, "exec_env", "dev")
    db_path = tmp_path / "repom_dev.sqlite3"

    db_engine, db_test = create_fixtures(
        db_url=f"{driver}:///{db_path}", allow_destructive=True
    )

    assert callable(db_engine)
    assert callable(db_test)
    assert not db_path.exists()
