"""Safety guard tests for create_test_fixtures (repom#135).

create_test_fixtures drops every table in Base.metadata when its
session-scoped engine fixture tears down. These tests verify the factory
refuses to target a non-test, non-in-memory database unless the caller opts
in explicitly.
"""


import sqlite3

import pytest
from sqlalchemy.engine import URL

from repom.config import config
from repom.testing import (
    _is_in_memory_sqlite_url,
    _require_test_database,
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
        ("sqlite:///file:///tmp/memdb?mode=memory&uri=true", True),
        ("sqlite:///file::memory:?uri=true", True),
        ("sqlite:///file:real1.db#?mode=memory&uri=true", False),
        ("sqlite+pysqlite:///file:real1.db#?mode=memory&uri=true", False),
        ("sqlite+aiosqlite:///file:real1.db#?mode=memory&uri=true", False),
        ("sqlite:///file:real5.db#frag?uri=true&mode=memory&cache=shared", False),
        ("sqlite:///file:real6.db#:memory:?mode=memory&uri=true", False),
        ("sqlite:///file:///tmp/real9.db#?mode=memory&uri=true", False),
        ("sqlite:///file:memdb#?mode=memory&uri=true", False),
        ("sqlite:///file::memory:#frag?cache=shared&uri=true", False),
        ("sqlite:///file:memdb?mode=memory&uri=true#", False),
        ("sqlite:///file:real%23.db?mode=memory&uri=true", False),
        ("sqlite:///file:real%3F.db?mode=memory&uri=true", False),
        ("sqlite:///file:real%3f.db?mode=memory&uri=true", False),
        ("sqlite:///file:real%00.db?mode=memory&uri=true", False),
        ("sqlite:///file:x%25y?mode=memory&uri=true", False),
        ("sqlite:///file:mem%20db?mode=memory&uri=true", False),
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


def _format_url(template, driver, tmp_path):
    return template.format(driver=driver, path=tmp_path.as_posix().lstrip("/"))


def _create_sentinel_database(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    return db_path


def _read_sentinel(db_path):
    with sqlite3.connect(db_path) as connection:
        return connection.execute("SELECT value FROM sentinel").fetchone()


# SQLite ignores everything after "#" in a URI, so "mode=memory" placed after it
# never takes effect and the named file is opened read-write (repom#296).
# "%" escapes are refused too: SQLite decodes them after the check has run.
_REJECTED_FILE_URI_TEMPLATES = [
    pytest.param("{driver}:///file:real.db#?mode=memory&uri=true", id="empty-fragment"),
    pytest.param(
        "{driver}:///file:real.db#frag?uri=true&mode=memory&cache=shared",
        id="fragment-text",
    ),
    pytest.param(
        "{driver}:///file:real.db#:memory:?mode=memory&uri=true", id="memory-marker-fragment"
    ),
    pytest.param(
        "{driver}:///file:///{path}/real.db#?mode=memory&uri=true", id="absolute-path"
    ),
    pytest.param(
        "{driver}:///file::memory:#frag?cache=shared&uri=true", id="memory-filename-fragment"
    ),
    pytest.param("{driver}:///file:real%23.db?mode=memory&uri=true", id="escaped-hash"),
    pytest.param("{driver}:///file:real%3F.db?mode=memory&uri=true", id="escaped-question"),
    pytest.param(
        "{driver}:///file:real%3f.db?mode=memory&uri=true", id="escaped-question-lowercase"
    ),
    pytest.param("{driver}:///file:real%00.db?mode=memory&uri=true", id="escaped-nul"),
    pytest.param("{driver}:///file:real%25.db?mode=memory&uri=true", id="escaped-percent"),
]


@pytest.mark.parametrize("driver", ["sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"])
@pytest.mark.parametrize("template", _REJECTED_FILE_URI_TEMPLATES)
def test_require_test_database_rejects_file_uris_that_hide_the_memory_mode(
    tmp_path, monkeypatch, driver, template
):
    monkeypatch.setattr(config, "exec_env", "dev")
    monkeypatch.chdir(tmp_path)
    real_db = _create_sentinel_database(tmp_path / "real.db")
    db_url = _format_url(template, driver, tmp_path)

    with pytest.raises(RuntimeError, match="Refusing to create test fixtures"):
        _require_test_database(db_url, allow_destructive=False)

    assert _require_test_database(db_url, allow_destructive=True) is None
    assert _read_sentinel(real_db) == ("preserved",)
    assert [path.name for path in tmp_path.iterdir()] == ["real.db"]


@pytest.mark.parametrize(
    ("create_fixtures", "driver"),
    [
        (create_test_fixtures, "sqlite"),
        (create_async_test_fixtures, "sqlite+aiosqlite"),
    ],
)
@pytest.mark.parametrize("template", _REJECTED_FILE_URI_TEMPLATES)
def test_fixture_factories_reject_file_uris_that_hide_the_memory_mode(
    tmp_path, monkeypatch, create_fixtures, driver, template
):
    monkeypatch.setattr(config, "exec_env", "dev")
    monkeypatch.chdir(tmp_path)
    real_db = _create_sentinel_database(tmp_path / "real.db")
    db_url = _format_url(template, driver, tmp_path)

    with pytest.raises(RuntimeError, match="Refusing to create test fixtures"):
        create_fixtures(db_url=db_url, model_loader=lambda: None)

    assert _read_sentinel(real_db) == ("preserved",)
    assert [path.name for path in tmp_path.iterdir()] == ["real.db"]


# SQLAlchemy 2.1 percent-decodes url.database, so the escaped names above reach the
# check in these decoded forms; 2.0 keeps the escapes. Feeding the decoded forms
# through make_url makes the 2.1 behavior testable on either version (repom#301).
_DECODED_FILE_URI_DATABASES = [
    pytest.param("file:real?.db", id="question"),
    pytest.param("file:x#y", id="hash"),
    pytest.param("file:x%y", id="percent"),
    pytest.param("file:mem db", id="space"),
    pytest.param("file:x\x00y", id="nul"),
    pytest.param("file:x\ty", id="tab"),
    pytest.param("file:x\x7fy", id="delete"),
]


def _patch_make_url_with_decoded_database(monkeypatch, database):
    url = URL.create(
        "sqlite", database=database, query={"mode": "memory", "uri": "true"}
    )
    monkeypatch.setattr("repom.testing.make_url", lambda db_url: url)


@pytest.mark.parametrize("database", _DECODED_FILE_URI_DATABASES)
def test_in_memory_sqlite_url_classifier_rejects_decoded_database_names(
    monkeypatch, database
):
    _patch_make_url_with_decoded_database(monkeypatch, database)

    assert _is_in_memory_sqlite_url("sqlite:///decoded?mode=memory&uri=true") is False


@pytest.mark.parametrize(
    "create_fixtures", [create_test_fixtures, create_async_test_fixtures]
)
@pytest.mark.parametrize("database", _DECODED_FILE_URI_DATABASES)
def test_fixture_factories_reject_decoded_file_uri_database_names(
    monkeypatch, create_fixtures, database
):
    monkeypatch.setattr(config, "exec_env", "dev")
    _patch_make_url_with_decoded_database(monkeypatch, database)

    with pytest.raises(RuntimeError, match="Refusing to create test fixtures"):
        create_fixtures(
            db_url="sqlite:///decoded?mode=memory&uri=true", model_loader=lambda: None
        )


# Every form the memory check accepts. Connecting through the fixture must
# neither fail on the engine settings nor create a file on disk.
_ACCEPTED_MEMORY_URL_TEMPLATES = [
    pytest.param("{driver}://", id="bare"),
    pytest.param("{driver}:///:memory:", id="memory-filename"),
    pytest.param("{driver}:///file:memdb?mode=memory&uri=true", id="uri-mode-memory"),
    pytest.param(
        "{driver}:///file:memdb?mode=memory&cache=private&uri=true", id="uri-cache-private"
    ),
    pytest.param(
        "{driver}:///file:memdb?mode=memory&cache=shared&uri=true", id="uri-cache-shared"
    ),
    pytest.param("{driver}:///file::memory:?cache=shared&uri=true", id="uri-memory-filename"),
    pytest.param(
        "{driver}:///file:///{path}/memdb?mode=memory&uri=true", id="uri-absolute-path"
    ),
]


@pytest.mark.parametrize("driver", ["sqlite", "sqlite+pysqlite"])
@pytest.mark.parametrize("template", _ACCEPTED_MEMORY_URL_TEMPLATES)
def test_sync_fixture_accepted_memory_urls_create_no_file(
    tmp_path, monkeypatch, driver, template
):
    monkeypatch.setattr(config, "exec_env", "dev")
    monkeypatch.chdir(tmp_path)
    db_url = _format_url(template, driver, tmp_path)
    assert _is_in_memory_sqlite_url(db_url)

    db_engine, _ = create_test_fixtures(db_url=db_url, model_loader=lambda: None)
    engine_generator = db_engine.__wrapped__()
    engine = next(engine_generator)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar() == 1
    finally:
        next(engine_generator, None)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("template", _ACCEPTED_MEMORY_URL_TEMPLATES)
async def test_async_fixture_accepted_memory_urls_create_no_file(
    tmp_path, monkeypatch, template
):
    monkeypatch.setattr(config, "exec_env", "dev")
    monkeypatch.chdir(tmp_path)
    db_url = _format_url(template, "sqlite+aiosqlite", tmp_path)
    assert _is_in_memory_sqlite_url(db_url)

    async_db_engine, _ = create_async_test_fixtures(
        db_url=db_url, model_loader=lambda: None
    )
    engine_generator = async_db_engine.__wrapped__()
    engine = await anext(engine_generator)
    try:
        async with engine.connect() as connection:
            result = await connection.exec_driver_sql("SELECT 1")
            assert result.scalar() == 1
    finally:
        await anext(engine_generator, None)

    assert list(tmp_path.iterdir()) == []
