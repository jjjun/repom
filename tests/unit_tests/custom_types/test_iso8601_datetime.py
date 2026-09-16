from tests._init import *
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import StatementError
from repom.custom_types.ISO8601DateTime import ISO8601DateTime
from repom.custom_types.ISO8601DateTimeStr import ISO8601DateTimeStr
from repom.models.base_model import BaseModel
from datetime import datetime
from typing import Optional


class Iso8601DateTimeModel(BaseModel):
    __tablename__ = 'test_model_iso8601_datetime'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[Optional[datetime]] = mapped_column(ISO8601DateTime, nullable=True)


class Iso8601DateTimeStrModel(BaseModel):
    __tablename__ = 'test_model_iso8601_datetime_str'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[Optional[datetime]] = mapped_column(ISO8601DateTimeStr, nullable=True)


@pytest.fixture(scope='function', autouse=True)
def setup_tables(setup_database_tables):
    """setup_database_tables に依存して、テーブルが作成されることを保証"""
    pass


def test_iso8601_datetime_roundtrip_datetime(db_test):
    value = datetime(2026, 1, 1, 12, 30, 0)
    record = Iso8601DateTimeModel(value=value)
    db_test.add(record)
    db_test.commit()
    db_test.expire_all()

    retrieved = db_test.query(Iso8601DateTimeModel).filter_by(id=record.id).first()
    assert retrieved.value == value


def test_iso8601_datetime_roundtrip_none(db_test):
    record = Iso8601DateTimeModel(value=None)
    db_test.add(record)
    db_test.commit()
    db_test.expire_all()

    retrieved = db_test.query(Iso8601DateTimeModel).filter_by(id=record.id).first()
    assert retrieved.value is None


def test_iso8601_datetime_raises_on_invalid_input(db_test):
    with pytest.raises(StatementError):
        record = Iso8601DateTimeModel(value="not-a-datetime")
        db_test.add(record)
        db_test.commit()


def test_iso8601_datetime_str_roundtrip_datetime(db_test):
    value = datetime(2026, 1, 1, 12, 30, 0)
    record = Iso8601DateTimeStrModel(value=value)
    db_test.add(record)
    db_test.commit()
    db_test.expire_all()

    retrieved = db_test.query(Iso8601DateTimeStrModel).filter_by(id=record.id).first()
    assert retrieved.value == value


def test_iso8601_datetime_str_roundtrip_none(db_test):
    record = Iso8601DateTimeStrModel(value=None)
    db_test.add(record)
    db_test.commit()
    db_test.expire_all()

    retrieved = db_test.query(Iso8601DateTimeStrModel).filter_by(id=record.id).first()
    assert retrieved.value is None


def test_iso8601_datetime_str_raises_on_invalid_input(db_test):
    with pytest.raises(StatementError):
        record = Iso8601DateTimeStrModel(value="not-a-datetime")
        db_test.add(record)
        db_test.commit()
