"""UTCDateTime round trips on PostgreSQL when its integration DB is enabled."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select

from repom.custom_types import UTCDateTime


POSTGRES_INTEGRATION_ENABLED = os.getenv('DB_TYPE') == 'postgres'


def _postgres_datetime_table():
    metadata = MetaData()
    table = Table(
        f'utc_datetime_{uuid4().hex}',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('value', UTCDateTime(), nullable=True),
        prefixes=['TEMPORARY'],
    )
    return metadata, table


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


@pytest.mark.skipif(
    not POSTGRES_INTEGRATION_ENABLED,
    reason='PostgreSQL integration requires DB_TYPE=postgres and a running server',
)
def test_utc_datetime_round_trips_on_postgresql():
    from repom.database import get_sync_engine

    engine = get_sync_engine()
    metadata, table = _postgres_datetime_table()
    values, expected_values = _datetime_values()

    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            for value_id, value in enumerate(values, start=1):
                connection.execute(insert(table).values(id=value_id, value=value))
            results = connection.execute(
                select(table.c.value).order_by(table.c.id)
            ).scalars().all()
            metadata.drop_all(connection)
    finally:
        engine.dispose()

    assert results == expected_values
    assert results[0] is None
    assert all(value is None or value.tzinfo == timezone.utc for value in results)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not POSTGRES_INTEGRATION_ENABLED,
    reason='PostgreSQL integration requires DB_TYPE=postgres and a running server',
)
async def test_async_utc_datetime_round_trips_on_postgresql():
    from repom.database import get_async_engine

    engine = await get_async_engine()
    metadata, table = _postgres_datetime_table()
    values, expected_values = _datetime_values()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            for value_id, value in enumerate(values, start=1):
                await connection.execute(insert(table).values(id=value_id, value=value))
            result = await connection.execute(
                select(table.c.value).order_by(table.c.id)
            )
            results = result.scalars().all()
            await connection.run_sync(metadata.drop_all)
    finally:
        await engine.dispose()

    assert results == expected_values
    assert results[0] is None
    assert all(value is None or value.tzinfo == timezone.utc for value in results)
