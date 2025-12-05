from typing import Any

from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from tests._init import *

from repom.base_model import BaseModel
from repom.custom_types.CustomJSON import CustomJSON


class CustomJsonModel(BaseModel):
    __tablename__ = "custom_json_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[Any] = mapped_column(CustomJSON, nullable=True)


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
