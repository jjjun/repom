from tests._init import *
from typing import Any
from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from repom.models.base_model import BaseModel


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
