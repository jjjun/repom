from tests._init import *

import time
from datetime import datetime, timezone

from sqlalchemy import String, event
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel


class UpdatedAtBumpModel(BaseModel):
    __tablename__ = 'updated_at_bump_models'
    use_updated_at = True

    name: Mapped[str] = mapped_column(String(50), default='')


def _capture_update_statements(session):
    statements = []

    def capture_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(session.bind, 'before_cursor_execute', capture_statement)

    def stop_capture():
        event.remove(session.bind, 'before_cursor_execute', capture_statement)

    return statements, stop_capture


def test_unchanged_value_reassignment_emits_no_update_and_keeps_updated_at(db_test):
    """既存値と同じ値を再代入しても UPDATE は発行されず updated_at も変わらないこと"""
    record = UpdatedAtBumpModel(name='alice')
    db_test.add(record)
    db_test.commit()
    original_updated_at = record.updated_at

    record.name = record.name
    statements, stop_capture = _capture_update_statements(db_test)
    try:
        db_test.commit()
    finally:
        stop_capture()

    assert not any(
        statement.lstrip().upper().startswith('UPDATE') for statement in statements
    )
    assert record.updated_at == original_updated_at


def test_changed_column_bumps_updated_at(db_test):
    """カラムの値を実際に変更した場合は updated_at が更新されること"""
    record = UpdatedAtBumpModel(name='alice')
    db_test.add(record)
    db_test.commit()
    original_updated_at = record.updated_at

    time.sleep(0.05)
    record.name = 'bob'
    db_test.commit()

    assert record.updated_at > original_updated_at


def test_explicit_updated_at_assignment_is_preserved(db_test):
    """updated_at に明示的な値を代入した場合、自動更新で上書きされないこと"""
    record = UpdatedAtBumpModel(name='alice')
    db_test.add(record)
    db_test.commit()

    chosen = datetime(2000, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    record.name = 'bob'
    record.updated_at = chosen
    db_test.commit()

    assert record.updated_at == chosen


@pytest.mark.asyncio
async def test_unchanged_value_reassignment_keeps_updated_at_async(async_db_test):
    """AsyncSession でも既存値と同じ値の再代入で updated_at が変わらないこと"""
    record = UpdatedAtBumpModel(name='alice')
    async_db_test.add(record)
    await async_db_test.commit()
    original_updated_at = record.updated_at

    record.name = record.name
    await async_db_test.commit()

    assert record.updated_at == original_updated_at
