import json
from typing import Any

import pytest
from sqlalchemy import ARRAY, JSON, TEXT, Integer, String, Text, event, text
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from repom import AsyncBaseRepository, BaseRepository, NulByteError
from repom.custom_types.CustomJSON import CustomJSON
from repom.custom_types.ListJSON import ListJSON
from repom.models.base_model import BaseModel


class PipeJoined(TypeDecorator):
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = '|'.join(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.split('|')
        return value


class JSONOverText(TypeDecorator):
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


def _contains_nul_byte(value):
    if isinstance(value, str):
        return '\0' in value
    if isinstance(value, dict):
        return any(
            _contains_nul_byte(key) or _contains_nul_byte(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_nul_byte(item) for item in value)
    return False


class NulByteModel(BaseModel):
    __tablename__ = 'nul_byte_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    custom_payload: Mapped[Any] = mapped_column(CustomJSON, nullable=True)
    list_payload: Mapped[list] = mapped_column(ListJSON, nullable=True)
    payload: Mapped[Any] = mapped_column(JSON, nullable=True)
    array_payload: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON, 'sqlite'), nullable=True
    )
    encoded_payload: Mapped[Any] = mapped_column(JSONOverText, nullable=True)
    pipe_payload: Mapped[list] = mapped_column(PipeJoined, nullable=True)


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


@pytest.mark.parametrize(
    ('value', 'key_path'),
    [
        ('bad\0value', '$'),
        ({'nested': {'value': 'bad\0value'}}, 'nested.value'),
        ({'items': [{'name': 'bad\0value'}]}, 'items[0].name'),
        ({'bad\0key': 'value'}, 'bad\0key'),
    ],
)
def test_json_columns_reject_nul_bytes_with_key_path(db_test, value, key_path):
    record = NulByteModel(
        title='valid',
        body='valid',
        payload=value,
    )
    db_test.add(record)

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == 'nul_byte_models.payload'
    assert exc_info.value.key_path == key_path
    if '\0' in key_path:
        assert key_path.replace('\0', '\\u0000') in str(exc_info.value)
        assert chr(0) not in str(exc_info.value)
    else:
        assert key_path in str(exc_info.value)


@pytest.mark.parametrize(
    ('field', 'value', 'key_path'),
    [
        ('custom_payload', {'nested': 'bad\0value'}, 'nested'),
        ('list_payload', [{'nested': 'bad\0value'}], '[0].nested'),
        ('array_payload', ['bad\0value'], '[0]'),
    ],
)
def test_json_decorators_and_string_arrays_reject_nul_bytes(
    db_test, field, value, key_path
):
    db_test.add(NulByteModel(title='valid', body='valid', **{field: value}))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == f'nul_byte_models.{field}'
    assert exc_info.value.key_path == key_path


def test_json_columns_preserve_escaped_nul_text_and_control_characters(db_test):
    value = {
        'note': 'ordinary prose: \\u0000',
        'text': '日本語\nwith a newline',
    }
    record = NulByteModel(title='valid', body='valid', payload=value)
    db_test.add(record)
    db_test.flush()
    db_test.expire_all()

    assert db_test.get(NulByteModel, record.id).payload == value


@pytest.mark.parametrize(
    ('value', 'key_path'),
    [
        ({'nested': 'bad\0value'}, 'nested'),
        ({'bad\0key': 'value'}, 'bad\0key'),
        ({'items': ['bad\0value']}, 'items[0]'),
    ],
)
def test_json_over_text_rejects_nul_bytes_with_key_path(db_test, value, key_path):
    db_test.add(NulByteModel(title='valid', body='valid', encoded_payload=value))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == 'nul_byte_models.encoded_payload'
    assert exc_info.value.key_path == key_path


def test_json_over_text_preserves_escaped_nul_prose(db_test):
    value = {'note': 'ordinary prose: \\u0000'}
    record = NulByteModel(title='valid', body='valid', encoded_payload=value)
    db_test.add(record)
    db_test.flush()
    db_test.expire_all()

    assert db_test.get(NulByteModel, record.id).encoded_payload == value


def test_json_column_update_rejects_nul_bytes(db_test):
    record = NulByteModel(title='valid', body='valid', payload={'value': 'valid'})
    db_test.add(record)
    db_test.flush()
    record.payload = {'value': 'bad\0value'}

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.key_path == 'value'


def test_text_type_decorator_rejects_nul_bytes_with_key_path(db_test):
    db_test.add(
        NulByteModel(title='valid', body='valid', pipe_payload=['valid', 'bad\0value'])
    )

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == 'nul_byte_models.pipe_payload'
    assert exc_info.value.key_path == '[1]'


def test_json_over_text_detection_distinguishes_poisoned_and_prose_rows(db_test):
    poisoned = '{"note": "bad\\u0000value"}'
    prose = '{"note": "ordinary prose: \\\\u0000"}'
    db_test.execute(
        text(
            'INSERT INTO nul_byte_models (title, body, encoded_payload) '
            'VALUES (:title, :body, :encoded_payload)'
        ),
        [
            {'title': 'poisoned', 'body': 'valid', 'encoded_payload': poisoned},
            {'title': 'prose', 'body': 'valid', 'encoded_payload': prose},
        ],
    )

    candidates = db_test.execute(
        text(
            "SELECT id, encoded_payload FROM nul_byte_models "
            "WHERE instr(encoded_payload, char(92) || 'u0000') > 0"
        )
    )
    poisoned_ids = [
        row.id
        for row in candidates
        if _contains_nul_byte(json.loads(row.encoded_payload))
    ]

    assert poisoned_ids == [1]


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


@pytest.mark.run_benchmark
def test_bulk_insert_json_nul_byte_guard_benchmark(db_engine, benchmark):
    session = sessionmaker(bind=db_engine)()
    payload = {
        'items': [
            {'name': f'item {index}', 'description': 'realistic payload text' * 10}
            for index in range(100)
        ]
    }

    def bulk_insert():
        records = [
            NulByteModel(
                title=f'title {index}', body='realistic text body', payload=payload
            )
            for index in range(1_000)
        ]
        session.add_all(records)
        session.flush()
        session.rollback()

    try:
        benchmark(bulk_insert)
    finally:
        session.close()
