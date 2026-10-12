import sqlite3

import pytest
from sqlalchemy import String, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine, create_engine, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

import repom
from repom import insert_for_dialect
from repom.models.base_model import BaseModel
from repom.repositories import insert_for_dialect as repository_insert_for_dialect


class DialectInsertTestModel(BaseModel):
    __tablename__ = 'dialect_insert_test_items'

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)


def test_insert_for_dialect_is_exported_from_public_packages():
    assert insert_for_dialect is repository_insert_for_dialect
    assert 'insert_for_dialect' in repom.__all__
    assert 'insert_for_dialect' in repom.repositories.__all__


@pytest.mark.parametrize(
    ('target', 'dialect_name'),
    [
        ('sqlite', 'sqlite'),
        (sqlite.dialect(), 'sqlite'),
        ('postgresql', 'postgresql'),
        (postgresql.dialect(), 'postgresql'),
    ],
)
def test_insert_for_dialect_accepts_dialect_name_or_dialect(target, dialect_name):
    statement = insert_for_dialect(target, DialectInsertTestModel)
    dialect = (
        sqlite.dialect()
        if dialect_name == 'sqlite'
        else postgresql.dialect()
    )

    assert statement.compile(dialect=dialect)


@pytest.mark.parametrize(
    ('target', 'dialect_name'),
    [
        ('mysql', 'mysql'),
        ('mariadb', 'mariadb'),
    ],
)
def test_insert_for_dialect_rejects_unsupported_dialects(target, dialect_name):
    with pytest.raises(NotImplementedError, match=dialect_name):
        insert_for_dialect(target, DialectInsertTestModel)


@pytest.mark.parametrize('dialect_name', ['sqlite', 'postgresql'])
def test_insert_for_dialect_resolves_engine_and_session(db_engine, dialect_name):
    if dialect_name == 'sqlite':
        engine = db_engine
        dialect = sqlite.dialect()
    else:
        engine = create_engine('postgresql+psycopg://')
        dialect = postgresql.dialect()

    try:
        for target in (engine, Session(bind=engine)):
            statement = insert_for_dialect(target, DialectInsertTestModel)
            assert statement.compile(dialect=dialect)
    finally:
        if dialect_name == 'postgresql':
            engine.dispose()


def test_insert_for_dialect_resolves_connection(db_engine):
    with db_engine.connect() as connection:
        statement = insert_for_dialect(connection, DialectInsertTestModel)

    assert statement.compile(dialect=sqlite.dialect())


def test_insert_for_dialect_resolves_postgresql_connection():
    engine = Engine(
        StaticPool(creator=lambda: sqlite3.connect(':memory:')),
        postgresql.dialect(dbapi=sqlite3),
        make_url('postgresql://'),
    )
    try:
        with engine.connect() as connection:
            statement = insert_for_dialect(connection, DialectInsertTestModel)
    finally:
        engine.dispose()

    assert statement.compile(dialect=postgresql.dialect())


@pytest.mark.parametrize(
    ('url', 'dialect'),
    [
        ('sqlite+aiosqlite:///:memory:', sqlite.dialect()),
        ('postgresql+asyncpg://', postgresql.dialect()),
    ],
)
@pytest.mark.asyncio
async def test_insert_for_dialect_resolves_async_session(url, dialect):
    engine = create_async_engine(url)
    try:
        async with AsyncSession(bind=engine) as session:
            statement = insert_for_dialect(session, DialectInsertTestModel)
            assert statement.compile(dialect=dialect)
    finally:
        await engine.dispose()


def test_insert_for_dialect_compiles_postgresql_upsert():
    statement = insert_for_dialect(
        'postgresql', DialectInsertTestModel
    ).values(key='external-1', value='first')
    statement = statement.on_conflict_do_nothing(
        index_elements=[DialectInsertTestModel.key]
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert 'ON CONFLICT' in sql
    assert 'DO NOTHING' in sql


def test_insert_for_dialect_upserts_against_sqlite_fixture(db_test):
    session = db_test()
    statement = insert_for_dialect(session, DialectInsertTestModel).values(
        key='external-1',
        value='first',
    )
    session.execute(statement)

    update = insert_for_dialect(session, DialectInsertTestModel).values(
        key='external-1',
        value='updated',
    )
    update = update.on_conflict_do_update(
        index_elements=[DialectInsertTestModel.key],
        set_={'value': update.excluded.value},
    )
    session.execute(update)

    row = session.scalar(
        select(DialectInsertTestModel).where(
            DialectInsertTestModel.key == 'external-1'
        )
    )

    assert row is not None
    assert row.value == 'updated'
