from typing import Any

from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

import pytest

from repom.models.base_model import BaseModel
from repom.custom_types.CustomJSON import CustomJSON


class CustomJsonModel(BaseModel):
    __tablename__ = "custom_json_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[Any] = mapped_column(CustomJSON, nullable=True)


@pytest.fixture(scope='function', autouse=True)
def setup_tables(setup_database_tables):
    """setup_database_tables に依存して、テーブルが作成されることを保証"""
    pass


def test_custom_json_python_type_is_undeclared():
    with pytest.raises(NotImplementedError):
        CustomJSON().python_type


def test_custom_json_none_saved_as_null(db_test):
    """CustomJSON カラムに None を保存すると DB では NULL が保存されることを確認する。"""
    record = CustomJsonModel(payload=None)
    db_test.add(record)
    db_test.commit()

    raw_value = db_test.connection().execute(
        text("SELECT payload FROM custom_json_models WHERE id = :id"),
        {"id": record.id},
    ).scalar_one()

    assert record.payload is None
    assert raw_value is None


def test_custom_json_round_trips_non_none_value(db_test):
    payload = {"enabled": True, "items": [1, "two", None]}
    record = CustomJsonModel(payload=payload)

    db_test.add(record)
    db_test.flush()
    db_test.expire(record, ["payload"])

    assert record.payload == payload


class JsonNullModel(BaseModel):
    __tablename__ = 'json_null_models'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[Any] = mapped_column(JSON, nullable=True)


def test_json_column_none_saved_as_null_string(db_test):
    """JSON カラムに None を保存すると 'null' が永続化されることを確認する。"""
    record = JsonNullModel(payload=None)
    db_test.add(record)
    db_test.commit()

    raw_value = db_test.connection().execute(
        text("SELECT payload FROM json_null_models WHERE id = :id"),
        {"id": record.id},
    ).scalar_one()

    assert record.payload is None
    assert raw_value == 'null'
