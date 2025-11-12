from tests._init import *
from sqlalchemy import Column, Integer
from mine_db.custom_types.CreatedAt import CreatedAt
from tests.db_test_fixtures import db_test
from mine_db.base_model import BaseModel
from datetime import datetime, timedelta


class CreatedAtModel(BaseModel):
    __tablename__ = 'test_model_createdat'
    id = Column(Integer, primary_key=True)
    created_at = Column(CreatedAt, default=datetime.now)


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
