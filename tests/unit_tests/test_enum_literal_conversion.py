from enum import Enum as PyEnum
from typing import Literal

import pytest
from pydantic import ValidationError
from sqlalchemy import Enum as SQLAEnum
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model_auto import BaseModelAuto


class Status(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EnumLiteralModel(BaseModelAuto):
    __tablename__ = "test_enum_literal"

    status: Mapped[Status] = mapped_column(SQLAEnum(Status))


def test_enum_to_literal_conversion(db_test):
    """Enum 型が Literal に変換され、バリデーションが機能することを確認"""

    ResponseSchema = EnumLiteralModel.get_response_schema()

    status_field = ResponseSchema.model_fields["status"]
    assert status_field.annotation == Literal["active", "inactive"]

    valid_data = {"id": 1, "status": "active"}
    instance = ResponseSchema(**valid_data)
    assert instance.status == "active"

    invalid_data = {"id": 1, "status": "unknown"}
    with pytest.raises(ValidationError):
        ResponseSchema(**invalid_data)
