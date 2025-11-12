from tests._init import *
from sqlalchemy import Column, Integer
from sqlalchemy.exc import StatementError
from mine_db.custom_types.JSONEncoded import JSONEncoded
from tests.db_test_fixtures import db_test
from mine_db.base_model import BaseModel
from datetime import datetime


class MyModel(BaseModel):
    __tablename__ = 'test_model_jsonencoded'
    id = Column(Integer, primary_key=True)
    option_json = Column(JSONEncoded)


def test_json_encoded_value_is_json_format(db_test):
    option_data = {"key": "value"}
    log = MyModel(option_json=option_data)
    db_test.add(log)
    db_test.commit()
    assert log.option_json == option_data


def test_json_encoded_property_is_correct_type(db_test):
    option_data = ["item1", "item2"]
    log = MyModel(option_json=option_data)
    db_test.add(log)
    db_test.commit()
    assert isinstance(log.option_json, list)


def test_json_encoded_can_store_large_data(db_test):
    large_data = {"key": "a" * 2000}
    log = MyModel(option_json=large_data)
    db_test.add(log)
    db_test.commit()
    assert log.option_json == large_data


def test_json_encoded_column_retrieval(db_test):
    large_data = {"key": "a" * 2000}
    log = MyModel(option_json=large_data)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(MyModel).filter_by(id=log.id).first()
    assert retrieved_log.option_json == large_data


def test_json_encoded_with_primitive_types(db_test):
    string_data = "test_string"
    log = MyModel(option_json=string_data)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(MyModel).filter_by(id=log.id).first()
    assert retrieved_log.option_json == string_data

    int_data = 123
    log = MyModel(option_json=int_data)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(MyModel).filter_by(id=log.id).first()
    assert retrieved_log.option_json == int_data

    bool_data = True
    log = MyModel(option_json=bool_data)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(MyModel).filter_by(id=log.id).first()
    assert retrieved_log.option_json == bool_data
