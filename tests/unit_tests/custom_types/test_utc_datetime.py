from datetime import date, datetime, timedelta, timezone

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    create_engine,
    insert,
    select,
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from repom.custom_types import UTCDateTime
from repom.mixins import SoftDeletableMixin


def _datetime_table(metadata):
    return Table(
        'utc_datetime_test_values',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('value', UTCDateTime(), nullable=True),
    )


def _datetime_values():
    naive_value = datetime(2026, 4, 22, 12, 0, 0)
    offset_value = datetime(
        2026, 4, 22, 12, 0, 0, tzinfo=timezone(timedelta(hours=9))
    )
    return [None, naive_value, offset_value], [
        None,
        naive_value.replace(tzinfo=timezone.utc),
        offset_value.astimezone(timezone.utc),
    ]


def test_utc_datetime_round_trips_nullable_naive_and_offset_values_on_sqlite():
    engine = create_engine('sqlite:///:memory:')
    metadata = MetaData()
    table = _datetime_table(metadata)
    metadata.create_all(engine)
    values, expected_values = _datetime_values()

    with engine.begin() as connection:
        for value_id, value in enumerate(values, start=1):
            connection.execute(insert(table).values(id=value_id, value=value))
        results = connection.execute(
            select(table.c.value).order_by(table.c.id)
        ).scalars().all()

    engine.dispose()
    assert results == expected_values
    assert results[0] is None
    assert all(value is None or value.tzinfo == timezone.utc for value in results)


@pytest.mark.asyncio
async def test_utc_datetime_round_trips_nullable_naive_and_offset_values_on_aiosqlite():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    metadata = MetaData()
    table = _datetime_table(metadata)
    values, expected_values = _datetime_values()

    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        for value_id, value in enumerate(values, start=1):
            await connection.execute(insert(table).values(id=value_id, value=value))
        result = await connection.execute(select(table.c.value).order_by(table.c.id))
        results = result.scalars().all()

    await engine.dispose()
    assert results == expected_values
    assert results[0] is None
    assert all(value is None or value.tzinfo == timezone.utc for value in results)


def test_utc_datetime_normalizes_aware_result_values_to_utc():
    value = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone(timedelta(hours=-5)))

    result = UTCDateTime().process_result_value(value, None)

    assert result == value.astimezone(timezone.utc)
    assert result.tzinfo == timezone.utc


def test_utc_datetime_passes_non_datetime_bind_values_through_unchanged():
    value = date(2026, 4, 22)

    result = UTCDateTime().process_bind_param(value, None)

    assert result is value


def test_soft_delete_utc_datetime_has_no_alembic_schema_diff():
    class ExistingBase(DeclarativeBase):
        pass

    class CurrentBase(DeclarativeBase):
        pass

    class ExistingSoftDeleteModel(ExistingBase):
        __tablename__ = 'utc_datetime_schema_check'

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        deleted_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True, index=True
        )

    class CurrentSoftDeleteModel(CurrentBase, SoftDeletableMixin):
        __tablename__ = 'utc_datetime_schema_check'

        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    engine = create_engine('sqlite:///:memory:')
    existing_type = ExistingSoftDeleteModel.__table__.c.deleted_at.type
    current_type = CurrentSoftDeleteModel.__table__.c.deleted_at.type
    assert existing_type.compile(dialect=engine.dialect) == current_type.compile(
        dialect=engine.dialect
    )
    ExistingBase.metadata.create_all(engine)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        differences = compare_metadata(context, CurrentBase.metadata)
    engine.dispose()

    assert differences == []
