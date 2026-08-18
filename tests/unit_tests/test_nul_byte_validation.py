from typing import Any

import pytest
from sqlalchemy import Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from repom import AsyncBaseRepository, BaseRepository, NulByteError
from repom.custom_types.CustomJSON import CustomJSON
from repom.custom_types.ListJSON import ListJSON
from repom.custom_types.StrEncodedArray import StrEncodedArray
from repom.models.base_model import BaseModel


class NulByteModel(BaseModel):
    __tablename__ = 'nul_byte_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    custom_payload: Mapped[Any] = mapped_column(CustomJSON, nullable=True)
    list_payload: Mapped[list] = mapped_column(ListJSON, nullable=True)
    tags: Mapped[list] = mapped_column(StrEncodedArray, nullable=True)


class DeferredNulByteModel(BaseModel):
    __tablename__ = 'deferred_nul_byte_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text, deferred=True)


class NulByteRepository(BaseRepository[NulByteModel]):
    def __init__(self, session):
        super().__init__(NulByteModel, session)


class AsyncNulByteRepository(AsyncBaseRepository[NulByteModel]):
    def __init__(self, session):
        super().__init__(NulByteModel, session)


@pytest.mark.parametrize('field', ['title', 'body'])
def test_string_columns_reject_nul_bytes(db_test, field):
    values = {'title': 'valid', 'body': 'valid'}
    values[field] = 'bad\0value'
    db_test.add(NulByteModel(**values))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == f'nul_byte_models.{field}'
    assert exc_info.value.offset == 3


def test_string_columns_preserve_valid_control_characters(db_test):
    value = '\u65e5\u672c\u8a9e\n\t\x01\x1f'
    record = NulByteModel(title=value, body=value)
    db_test.add(record)
    db_test.flush()
    db_test.expire_all()

    stored = db_test.get(NulByteModel, record.id)

    assert stored.title == value
    assert stored.body == value


def test_nul_byte_error_reports_utf8_byte_offset(db_test):
    db_test.add(NulByteModel(title='\u65e5\u672c\u8a9e\0value', body='valid'))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.offset == 9


def test_json_columns_allow_nested_nul_bytes(db_test):
    record = NulByteModel(
        title='valid',
        body='valid',
        custom_payload={'nested': {'value': 'bad\0value'}},
        list_payload=[{'nested': 'bad\0value'}],
    )
    db_test.add(record)
    db_test.flush()

    assert record.id is not None


def test_str_encoded_array_rejects_nul_bytes(db_test):
    db_test.add(NulByteModel(title='valid', body='valid', tags=['bad\0value']))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.offset == 3


def test_bulk_update_rejects_nul_bytes(db_test):
    repo = NulByteRepository(session=db_test)
    record = repo.save(NulByteModel(title='valid', body='valid'))

    with pytest.raises(NulByteError) as exc_info:
        repo.bulk_update([{'id': record.id, 'title': 'bad\0value'}])

    assert exc_info.value.column_name == 'nul_byte_models.title'


@pytest.mark.asyncio
async def test_async_bulk_update_rejects_nul_bytes(async_db_test):
    repo = AsyncNulByteRepository(session=async_db_test)
    record = await repo.save(NulByteModel(title='valid', body='valid'))

    with pytest.raises(NulByteError) as exc_info:
        await repo.bulk_update([{'id': record.id, 'body': 'bad\0value'}])

    assert exc_info.value.column_name == 'nul_byte_models.body'


def test_update_skips_untouched_deferred_string_columns(db_test):
    record = DeferredNulByteModel(title='valid', body='large body')
    db_test.add(record)
    db_test.flush()
    record_id = record.id
    db_test.expunge(record)

    record = db_test.get(DeferredNulByteModel, record_id)
    statements = []

    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_test.bind, 'before_cursor_execute', capture_statement)
    try:
        record.title = 'updated'
        db_test.flush()
    finally:
        event.remove(db_test.bind, 'before_cursor_execute', capture_statement)

    assert not any(
        statement.lstrip().upper().startswith('SELECT') for statement in statements
    )


@pytest.mark.run_benchmark
def test_bulk_insert_nul_byte_guard_benchmark(db_engine, benchmark):
    session = sessionmaker(bind=db_engine)()

    def bulk_insert():
        records = [
            NulByteModel(title=f'title {index}', body='realistic text body')
            for index in range(1_000)
        ]
        session.add_all(records)
        session.flush()
        session.rollback()

    try:
        benchmark(bulk_insert)
    finally:
        session.close()
