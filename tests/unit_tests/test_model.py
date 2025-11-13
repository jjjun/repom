from tests._init import *
from sqlalchemy import Column, Integer, inspect
from datetime import datetime

from tests.db_test_fixtures import db_test
from repom.base_model import BaseModel


class CreatedAtModel(BaseModel):
    __tablename__ = 'created_at'
    use_created_at = True


class NoCreatedAtModel(BaseModel):
    __tablename__ = 'no_created_at'
    use_created_at = False


class DefaultIdModel(BaseModel):
    __tablename__ = 'default_id'


class UpdatedAtModel(BaseModel):
    __tablename__ = 'updated_at'
    use_updated_at = True


def test_use_created_at_true(db_test):
    """
    use_created_at=True の場合、created_at カラムが作成されること
    """
    inspector = inspect(CreatedAtModel)
    assert 'created_at' in [column.name for column in inspector.columns]


def test_use_created_at_false(db_test):
    """
    use_created_at=False の場合、created_at カラムが作成されないこと
    """
    inspector = inspect(NoCreatedAtModel)
    assert 'created_at' not in [column.name for column in inspector.columns]


def test_created_at_default_value(db_test):
    """
    created_at に現在日時刻が入ること
    """
    sample = CreatedAtModel()
    db_test.add(sample)
    db_test.commit()
    assert sample.created_at is not None
    assert isinstance(sample.created_at, datetime)


def test_default_id_column(db_test):
    """
    デフォルトで id カラムが作成されること
    """
    inspector = inspect(DefaultIdModel)
    assert 'id' in [column.name for column in inspector.columns]


def test_use_updated_at_true(db_test):
    """
    use_updated_at=True の場合、updated_at カラムが作成されること
    """
    inspector = inspect(UpdatedAtModel)
    assert 'updated_at' in [column.name for column in inspector.columns]
