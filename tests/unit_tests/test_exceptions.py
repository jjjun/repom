from types import SimpleNamespace

import pytest
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from repom.exceptions import is_unique_violation, unique_violation_constraint_name


def _integrity_error(original):
    return IntegrityError('statement', {}, original)


@pytest.mark.parametrize(
    'original',
    [SimpleNamespace(sqlstate='23505'), SimpleNamespace(pgcode='23505')],
)
def test_is_unique_violation_recognizes_postgresql_sqlstate(original):
    assert is_unique_violation(_integrity_error(original))


@pytest.mark.parametrize(
    'error_name',
    ['SQLITE_CONSTRAINT_UNIQUE', 'SQLITE_CONSTRAINT_PRIMARYKEY'],
)
def test_is_unique_violation_recognizes_sqlite_error_names(error_name):
    assert is_unique_violation(
        _integrity_error(SimpleNamespace(sqlite_errorname=error_name))
    )


def test_is_unique_violation_falls_back_to_message_for_unknown_drivers():
    assert is_unique_violation(_integrity_error(Exception('UNIQUE index conflict')))
    assert not is_unique_violation(_integrity_error(Exception('foreign key failed')))


def test_is_unique_violation_uses_postgresql_code_for_non_unique_errors():
    error = _integrity_error(
        SimpleNamespace(sqlstate='23503', message='unique key was not checked')
    )
    assert not is_unique_violation(error)


def test_is_unique_violation_rejects_non_unique_sqlite_constraints():
    error = _integrity_error(
        SimpleNamespace(
            sqlite_errorname='SQLITE_CONSTRAINT_FOREIGNKEY',
            message='unique key was not checked',
        )
    )
    assert not is_unique_violation(error)


def test_unique_violation_constraint_name_returns_driver_diagnostic():
    error = _integrity_error(
        SimpleNamespace(diag=SimpleNamespace(constraint_name='uq_account_email'))
    )
    assert unique_violation_constraint_name(error) == 'uq_account_email'


def test_unique_violation_constraint_name_returns_none_when_unavailable():
    error = _integrity_error(Exception('duplicate'))
    assert unique_violation_constraint_name(error) is None


def _unique_table():
    metadata = MetaData()
    table = Table(
        'unique_violation_test',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('value', String, unique=True),
    )
    return metadata, table


def test_is_unique_violation_recognizes_real_sqlite_unique_error():
    engine = create_engine('sqlite:///:memory:')
    metadata, table = _unique_table()
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(insert(table).values(value='duplicate'))

    try:
        with pytest.raises(IntegrityError) as error:
            with engine.begin() as connection:
                connection.execute(insert(table).values(value='duplicate'))
        assert error.value.orig.sqlite_errorname == 'SQLITE_CONSTRAINT_UNIQUE'
        assert is_unique_violation(error.value)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_is_unique_violation_recognizes_real_aiosqlite_unique_error():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    metadata, table = _unique_table()
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(insert(table).values(value='duplicate'))

    try:
        with pytest.raises(IntegrityError) as error:
            async with engine.begin() as connection:
                await connection.execute(insert(table).values(value='duplicate'))
        assert error.value.orig.sqlite_errorname == 'SQLITE_CONSTRAINT_UNIQUE'
        assert is_unique_violation(error.value)
    finally:
        await engine.dispose()
