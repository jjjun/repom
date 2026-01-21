from tests._init import *
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from repom.custom_types.AutoDateTime import AutoDateTime
from repom.models.base_model import BaseModel
from datetime import datetime, timedelta
from typing import Optional


class CreatedAtModel(BaseModel):
    __tablename__ = 'test_model_createdat'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(AutoDateTime, default=datetime.now)


def test_created_at_default_now(db_test):
    log = CreatedAtModel()
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(CreatedAtModel).filter_by(id=log.id).first()
    assert isinstance(retrieved_log.created_at, datetime)
    assert retrieved_log.created_at <= datetime.now()
    assert retrieved_log.created_at > datetime.now() - timedelta(seconds=10)


def test_created_at_with_provided_datetime(db_test):
    specific_time = datetime(2020, 1, 1, 12, 0, 0)
    log = CreatedAtModel(created_at=specific_time)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(CreatedAtModel).filter_by(id=log.id).first()
    assert retrieved_log.created_at == specific_time
