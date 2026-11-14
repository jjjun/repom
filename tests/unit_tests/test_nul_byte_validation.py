import json
from typing import Any

import pytest
from sqlalchemy import ARRAY, JSON, TEXT, Integer, String, Text, event, inspect, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker, synonym
from sqlalchemy.types import TypeDecorator

from repom import AsyncBaseRepository, BaseRepository, NulByteError
from repom.custom_types.CustomJSON import CustomJSON
from repom.custom_types.ListJSON import ListJSON
from repom.models.base_model import BaseModel
from repom.nul_bytes import _string_columns, validate_values_no_nul_bytes


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


class RenamedColumnNulByteModel(BaseModel):
    __tablename__ = 'renamed_column_nul_byte_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column('document_body', Text)


class AliasedKeyNulByteModel(BaseModel):
    __tablename__ = 'aliased_key_nul_byte_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nick: Mapped[str] = mapped_column('nick_col', String(100))
    nick_syn = synonym('nick')

    @hybrid_property
    def nick_hybrid(self):
        return self.nick

    @nick_hybrid.inplace.update_expression
    @classmethod
    def _nick_hybrid_update_expression(cls, value):
        return [(cls.nick, value)]


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


@pytest.mark.parametrize(
    ('value', 'key_path'),
    [
        (('bad\0value',), '[0]'),
        ({'items': ('bad\0value',)}, 'items[0]'),
    ],
)
def test_json_columns_reject_nul_bytes_in_tuples_with_key_path(db_test, value, key_path):
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


@pytest.mark.parametrize(
    ('value', 'key_path'),
    [
        (('bad\0value',), '[0]'),
        ({'items': ('bad\0value',)}, 'items[0]'),
    ],
)
def test_bulk_update_rejects_nul_bytes_in_tuple(db_test, value, key_path):
    repo = NulByteRepository(session=db_test)
    record = repo.save(NulByteModel(title='valid', body='valid'))

    with pytest.raises(NulByteError) as exc_info:
        repo.bulk_update([{'id': record.id, 'payload': value}])

    assert exc_info.value.column_name == 'nul_byte_models.payload'
    assert exc_info.value.key_path == key_path


@pytest.mark.asyncio
async def test_async_bulk_update_rejects_nul_bytes(async_db_test):
    repo = AsyncNulByteRepository(session=async_db_test)
    record = await repo.save(NulByteModel(title='valid', body='valid'))

    with pytest.raises(NulByteError) as exc_info:
        await repo.bulk_update([{'id': record.id, 'body': 'bad\0value'}])

    assert exc_info.value.column_name == 'nul_byte_models.body'


async def _insert_aliased_key_record(repository_adapter):
    repo = repository_adapter.repository_class(
        AliasedKeyNulByteModel, session=repository_adapter.session
    )
    (record,) = await repository_adapter.call(
        repo.bulk_insert, [AliasedKeyNulByteModel(nick='valid')]
    )
    return repo, record.id


def _bulk_update_selection(mode, record_id, row):
    if mode == 'id':
        return [{'id': record_id, **row}], {}
    if mode == 'filter_by':
        return [row], {'filter_by': {'id': record_id}}
    return [row], {'filters': [AliasedKeyNulByteModel.id == record_id]}


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['id', 'filter_by', 'filters'])
@pytest.mark.parametrize('key', ['nick', 'nick_col', 'nick_syn', 'nick_hybrid'])
async def test_bulk_update_rejects_nul_bytes_under_every_key_spelling(
    repository_adapter, key, mode
):
    repo, record_id = await _insert_aliased_key_record(repository_adapter)
    values, options = _bulk_update_selection(mode, record_id, {key: 'bad\0value'})

    if key == 'nick':
        with pytest.raises(NulByteError) as exc_info:
            await repository_adapter.call(repo.bulk_update, values, **options)
        assert exc_info.value.column_name == 'aliased_key_nul_byte_models.nick_col'
    else:
        with pytest.raises(TypeError, match=repr(key)):
            await repository_adapter.call(repo.bulk_update, values, **options)

    record = await repository_adapter.call(repo.get_by_id, record_id)
    assert record.nick == 'valid'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['id', 'filter_by', 'filters'])
@pytest.mark.parametrize('key', ['nick_col', 'nick_syn', 'nick_hybrid', 'missing', 1])
async def test_bulk_update_rejects_keys_that_are_not_mapped_column_attributes(
    repository_adapter, key, mode
):
    repo, record_id = await _insert_aliased_key_record(repository_adapter)
    values, options = _bulk_update_selection(mode, record_id, {key: 'changed'})

    with pytest.raises(TypeError, match='not a mapped column attribute'):
        await repository_adapter.call(repo.bulk_update, values, **options)

    record = await repository_adapter.call(repo.get_by_id, record_id)
    assert record.nick == 'valid'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['id', 'filter_by', 'filters'])
async def test_bulk_update_accepts_attribute_key_for_renamed_column(
    repository_adapter, mode
):
    repo, record_id = await _insert_aliased_key_record(repository_adapter)
    values, options = _bulk_update_selection(mode, record_id, {'nick': 'changed'})

    assert await repository_adapter.call(repo.bulk_update, values, **options) == 1

    record = await repository_adapter.call(repo.get_by_id, record_id)
    assert record.nick == 'changed'


@pytest.mark.asyncio
async def test_bulk_update_keeps_sql_expression_values_unvalidated(repository_adapter):
    repo, record_id = await _insert_aliased_key_record(repository_adapter)

    rowcount = await repository_adapter.call(
        repo.bulk_update,
        [{'id': record_id, 'nick': AliasedKeyNulByteModel.nick + '!'}],
    )

    assert rowcount == 1
    record = await repository_adapter.call(repo.get_by_id, record_id)
    assert record.nick == 'valid!'


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


def test_nul_guard_runs_for_renamed_column(db_test):
    db_test.add(RenamedColumnNulByteModel(title='valid', body='bad\0value'))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == 'renamed_column_nul_byte_models.document_body'
    assert exc_info.value.offset == 3


def test_nul_guard_runs_for_renamed_column_on_update(db_test):
    record = RenamedColumnNulByteModel(title='valid', body='valid')
    db_test.add(record)
    db_test.flush()
    record.body = 'bad\0value'

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert exc_info.value.column_name == 'renamed_column_nul_byte_models.document_body'


def test_nul_guard_runs_for_renamed_column_on_core_update():
    with pytest.raises(NulByteError) as exc_info:
        validate_values_no_nul_bytes(RenamedColumnNulByteModel, {'body': 'bad\0value'})

    assert exc_info.value.column_name == 'renamed_column_nul_byte_models.document_body'


def test_nul_guard_error_message_uses_db_column_name(db_test):
    db_test.add(RenamedColumnNulByteModel(title='valid', body='bad\0value'))

    with pytest.raises(NulByteError) as exc_info:
        db_test.flush()

    assert 'renamed_column_nul_byte_models.document_body' in str(exc_info.value)


def test_string_columns_keys_are_orm_attribute_names():
    mapper = inspect(RenamedColumnNulByteModel).mapper
    columns = {key: column_name for key, column_name, _ in _string_columns(mapper)}

    assert columns['body'] == 'renamed_column_nul_byte_models.document_body'
    assert 'document_body' not in columns


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
