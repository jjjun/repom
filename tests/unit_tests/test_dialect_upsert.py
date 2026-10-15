from datetime import datetime, timezone

import pytest
from sqlalchemy import Boolean, Index, String, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

import repom
from repom import NulByteError, build_insert_ignore, build_upsert
from repom.mixins import SoftDeletableMixin
from repom.models.base_model import BaseModel
from repom.repositories import (
    build_insert_ignore as repository_build_insert_ignore,
    build_upsert as repository_build_upsert,
)


class DialectUpsertModel(BaseModel, SoftDeletableMixin, use_created_at=True, use_updated_at=True):
    __tablename__ = 'dialect_upsert_test_items'

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    partial_key: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            'uq_dialect_upsert_test_items_partial_key_active',
            'partial_key',
            unique=True,
            sqlite_where=text('active = 1'),
        ),
    )


class DialectUpsertNoTimestampModel(BaseModel):
    __tablename__ = 'dialect_upsert_no_timestamp_test_items'

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


def test_upsert_builders_are_exported_from_public_packages():
    assert build_upsert is repository_build_upsert
    assert build_insert_ignore is repository_build_insert_ignore
    assert 'build_upsert' in repom.__all__
    assert 'build_insert_ignore' in repom.__all__
    assert 'build_upsert' in repom.repositories.__all__
    assert 'build_insert_ignore' in repom.repositories.__all__


def test_build_upsert_compiles_conflict_predicate_and_timestamp_updates():
    statement = build_upsert(
        'postgresql',
        DialectUpsertModel,
        {'partial_key': 'partial-1', 'value': 'first', 'active': True},
        conflict_columns=['partial_key'],
        update_columns=['value'],
        index_where=DialectUpsertModel.active.is_(True),
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert 'ON CONFLICT (partial_key) WHERE active IS true DO UPDATE SET' in sql
    assert 'value = excluded.value' in sql
    assert 'updated_at = excluded.updated_at' in sql
    assert 'created_at =' not in sql.split('DO UPDATE SET', maxsplit=1)[1]
    assert any(key.startswith('created_at') for key in compiled.params)
    assert any(key.startswith('updated_at') for key in compiled.params)


def test_build_upsert_rejects_empty_update_set_with_timestamps():
    with pytest.raises(ValueError, match='no columns to update; use insert_ignore'):
        build_upsert(
            'sqlite',
            DialectUpsertModel,
            {'key': 'empty-updates'},
            conflict_columns=['key'],
            update_columns=[],
        )

    with pytest.raises(ValueError, match='no columns to update; use insert_ignore'):
        build_upsert(
            'sqlite',
            DialectUpsertModel,
            {'key': 'conflict-only'},
            conflict_columns=['key'],
        )


def test_build_insert_ignore_rejects_duplicate_unhashable_conflict_keys():
    with pytest.raises(ValueError, match='duplicate conflict-column values'):
        build_insert_ignore(
            'sqlite',
            DialectUpsertModel,
            [{'key': {'id': 1}}, {'key': {'id': 1}}],
            conflict_columns=['key'],
        )


def test_build_insert_ignore_compiles_do_nothing():
    statement = build_insert_ignore(
        'postgresql',
        DialectUpsertModel,
        {'key': 'ignored-1', 'partial_key': 'partial-2', 'value': 'first', 'active': True},
        conflict_columns=[DialectUpsertModel.key],
    )

    assert 'ON CONFLICT (key) DO NOTHING' in str(statement.compile(dialect=postgresql.dialect()))


def test_build_upsert_accepts_connection_and_uses_supplied_updated_at(db_engine):
    updated_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    with db_engine.connect() as connection:
        statement = build_upsert(
            connection,
            DialectUpsertModel,
            {
                'key': 'connection-row',
                'partial_key': 'connection-partial',
                'value': 'value',
                'active': True,
                'updated_at': updated_at,
            },
            conflict_columns=['key'],
        )
        compiled = statement.compile(dialect=connection.dialect)

    assert 'updated_at = excluded.updated_at' in str(compiled)
    assert any(value == updated_at for key, value in compiled.params.items() if key.startswith('updated_at'))


@pytest.mark.asyncio
async def test_upsert_refreshes_loaded_model_and_advances_timestamps(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)
    inserted = await repository_adapter.call(
        repo.upsert,
        {'key': 'fresh-row', 'partial_key': 'fresh-partial', 'value': 'first', 'active': True},
        conflict_columns=['key'],
    )
    loaded = await repository_adapter.call(
        repository_adapter.session.scalar,
        select(DialectUpsertModel).where(DialectUpsertModel.key == 'fresh-row'),
    )
    created_at = loaded.created_at
    first_updated_at = loaded.updated_at

    updated = await repository_adapter.call(
        repo.upsert,
        {'key': 'fresh-row', 'partial_key': 'fresh-partial', 'value': 'second', 'active': True},
        conflict_columns=['key'],
    )

    assert inserted[0] is loaded
    assert updated == [loaded]
    assert loaded.value == 'second'
    assert loaded.created_at == created_at
    assert loaded.updated_at > first_updated_at


@pytest.mark.asyncio
async def test_internal_upsert_refreshes_timestamp_fields(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel)

    inserted = await repository_adapter.call(
        repo.upsert,
        {'key': 'internal-row', 'partial_key': 'internal-partial', 'value': 'value', 'active': True},
        conflict_columns=['key'],
    )

    assert inserted[0].id is not None
    assert inserted[0].created_at.tzinfo == timezone.utc
    assert inserted[0].updated_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_insert_ignore_returns_only_new_rows(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)
    await repository_adapter.call(
        repo.upsert,
        {'key': 'present-row', 'partial_key': 'present-partial', 'value': 'first', 'active': True},
        conflict_columns=['key'],
    )

    inserted = await repository_adapter.call(
        repo.insert_ignore,
        [
            {'key': 'present-row', 'partial_key': 'present-partial', 'value': 'ignored', 'active': True},
            {'key': 'new-row', 'partial_key': 'new-partial', 'value': 'inserted', 'active': True},
        ],
        conflict_columns=['key'],
    )

    assert [row.key for row in inserted] == ['new-row']


@pytest.mark.asyncio
async def test_upsert_where_false_skips_existing_row(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)
    await repository_adapter.call(
        repo.upsert,
        {'key': 'conditional-row', 'partial_key': 'conditional-partial', 'value': 'first', 'active': True},
        conflict_columns=['key'],
    )

    updated = await repository_adapter.call(
        repo.upsert,
        {'key': 'conditional-row', 'partial_key': 'conditional-partial', 'value': 'second', 'active': True},
        conflict_columns=['key'],
        where=DialectUpsertModel.value == 'does-not-match',
    )

    assert updated == []
    row = await repository_adapter.call(
        repository_adapter.session.scalar,
        select(DialectUpsertModel).where(DialectUpsertModel.key == 'conditional-row'),
    )
    assert row.value == 'first'


@pytest.mark.asyncio
async def test_upsert_uses_partial_unique_index(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)
    index_where = text('active = 1')
    first = await repository_adapter.call(
        repo.upsert,
        {'key': 'partial-first', 'partial_key': 'same-partial', 'value': 'first', 'active': True},
        conflict_columns=['partial_key'],
        index_where=index_where,
    )
    second = await repository_adapter.call(
        repo.upsert,
        {'key': 'partial-second', 'partial_key': 'same-partial', 'value': 'second', 'active': True},
        conflict_columns=['partial_key'],
        index_where=index_where,
    )

    assert first[0].id == second[0].id
    assert second[0].value == 'second'


@pytest.mark.asyncio
async def test_upsert_keeps_conflicting_soft_deleted_row_deleted(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)
    inserted = await repository_adapter.call(
        repo.upsert,
        {'key': 'deleted-row', 'partial_key': 'deleted-partial', 'value': 'first', 'active': True},
        conflict_columns=['key'],
    )
    await repository_adapter.call(repo.soft_delete, inserted[0].id)

    updated = await repository_adapter.call(
        repo.upsert,
        {'key': 'deleted-row', 'partial_key': 'deleted-partial', 'value': 'second', 'active': True},
        conflict_columns=['key'],
    )

    assert updated[0].value == 'second'
    assert updated[0].deleted_at is not None


@pytest.mark.asyncio
async def test_upsert_validation_errors(repository_adapter):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)
    valid = {'key': 'validation-row', 'partial_key': 'validation-partial', 'value': 'value', 'active': True}

    with pytest.raises(ValueError, match='at least one'):
        await repository_adapter.call(repo.insert_ignore, valid, conflict_columns=[])
    with pytest.raises(TypeError, match='mapped column'):
        await repository_adapter.call(
            repo.insert_ignore,
            {'key': 'unknown-row', 'missing': 'value'},
            conflict_columns=['key'],
        )
    with pytest.raises(ValueError, match='same set of keys'):
        await repository_adapter.call(
            repo.insert_ignore,
            [valid, {'key': 'different-row'}],
            conflict_columns=['key'],
        )
    with pytest.raises(ValueError, match='duplicate conflict'):
        await repository_adapter.call(
            repo.insert_ignore,
            [valid, valid],
            conflict_columns=['key'],
        )
    with pytest.raises(ValueError, match='conflict column'):
        await repository_adapter.call(
            repo.upsert,
            valid,
            conflict_columns=['key'],
            update_columns=['key'],
        )
    with pytest.raises(NulByteError):
        await repository_adapter.call(
            repo.insert_ignore,
            {'key': 'nul\x00row', 'partial_key': 'nul-partial', 'value': 'value', 'active': True},
            conflict_columns=['key'],
        )

    no_timestamp_repo = repository_adapter.repository_class(
        DialectUpsertNoTimestampModel, repository_adapter.session
    )
    with pytest.raises(ValueError, match='insert_ignore'):
        await repository_adapter.call(
            no_timestamp_repo.upsert,
            {'key': 'empty-updates'},
            conflict_columns=['key'],
            update_columns=[],
        )


@pytest.mark.asyncio
async def test_empty_values_return_without_executing(repository_adapter, monkeypatch):
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)

    if repository_adapter.mode == 'sync':
        monkeypatch.setattr(repository_adapter.session, 'execute', lambda *args, **kwargs: pytest.fail('unexpected execute'))
    else:
        async def fail_execute(*args, **kwargs):
            pytest.fail('unexpected execute')

        monkeypatch.setattr(repository_adapter.session, 'execute', fail_execute)

    assert await repository_adapter.call(repo.upsert, [], conflict_columns=['key']) == []
    assert await repository_adapter.call(repo.insert_ignore, [], conflict_columns=['key']) == []


@pytest.mark.asyncio
async def test_repository_methods_require_insert_returning(repository_adapter, monkeypatch):
    bind = repository_adapter.session.get_bind()
    monkeypatch.setattr(bind.dialect, 'insert_returning', False)
    repo = repository_adapter.repository_class(DialectUpsertModel, repository_adapter.session)

    with pytest.raises(NotImplementedError, match='SQLite 3.35 or later'):
        await repository_adapter.call(
            repo.upsert,
            {'key': 'returning-row', 'partial_key': 'returning-partial', 'value': 'value', 'active': True},
            conflict_columns=['key'],
        )
    with pytest.raises(NotImplementedError, match='SQLite 3.35 or later'):
        await repository_adapter.call(
            repo.insert_ignore,
            {'key': 'returning-row', 'partial_key': 'returning-partial', 'value': 'value', 'active': True},
            conflict_columns=['key'],
        )
