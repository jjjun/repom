from tests._init import *
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from repom.custom_types.AutoDateTime import AutoDateTime
from repom.models.base_model import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional


class CreatedAtModel(BaseModel):
    __tablename__ = 'test_model_createdat'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        AutoDateTime,
        default=lambda: datetime.now(timezone.utc)
    )


@pytest.fixture(scope='function', autouse=True)
def setup_tables(setup_database_tables):
    """setup_database_tables に依存して、テーブルが作成されることを保証"""
    pass


def test_created_at_default_now(db_test):
    now_utc = datetime.now(timezone.utc)
    log = CreatedAtModel()
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(CreatedAtModel).filter_by(id=log.id).first()
    assert isinstance(retrieved_log.created_at, datetime)
    assert retrieved_log.created_at.tzinfo == timezone.utc
    assert retrieved_log.created_at <= datetime.now(timezone.utc)
    assert retrieved_log.created_at > now_utc - timedelta(seconds=10)


def test_created_at_with_provided_naive_datetime(db_test):
    specific_time = datetime(2020, 1, 1, 12, 0, 0)
    log = CreatedAtModel(created_at=specific_time)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(CreatedAtModel).filter_by(id=log.id).first()
    assert retrieved_log.created_at == specific_time.replace(tzinfo=timezone.utc)


def test_process_bind_param_none_returns_aware_utc():
    value = AutoDateTime().process_bind_param(None, None)
    assert value is not None
    assert value.tzinfo == timezone.utc


def test_process_bind_param_naive_datetime_is_normalized_to_utc():
    naive_value = datetime(2026, 4, 22, 12, 0, 0)
    bound_value = AutoDateTime().process_bind_param(naive_value, None)
    assert bound_value == naive_value.replace(tzinfo=timezone.utc)


def test_process_bind_param_aware_datetime_is_preserved():
    aware_value = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
    bound_value = AutoDateTime().process_bind_param(aware_value, None)
    assert bound_value == aware_value


def test_process_result_value_naive_datetime_is_normalized_to_utc():
    naive_value = datetime(2026, 4, 22, 12, 0, 0)
    result_value = AutoDateTime().process_result_value(naive_value, None)
    assert result_value == naive_value.replace(tzinfo=timezone.utc)


def test_process_result_value_none_is_unchanged():
    assert AutoDateTime().process_result_value(None, None) is None
