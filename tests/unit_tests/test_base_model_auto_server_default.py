"""Tests for BaseModelAuto.get_create_schema and server_default handling"""

from tests._init import *
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model import Base
from repom.base_model_auto import BaseModelAuto


class ServerDefaultModel(BaseModelAuto):
    """server_default を持つ非NULLカラムを持つモデル"""

    __tablename__ = 'server_default_model'

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending'"),
        info={'description': 'ステータス（DBサーバーデフォルトで設定）'},
    )


def test_create_schema_treats_server_default_as_required():
    """server_default がある非NULLカラムが create スキーマで必須になることを確認"""
    CreateSchema = ServerDefaultModel.get_create_schema()

    status_field = CreateSchema.model_fields['status']

    assert status_field.is_required()


def test_server_default_applied_without_payload(db_test):
    """DB サーバーデフォルトが適用され、API 入力とズレる可能性があることを確認"""
    Base.metadata.create_all(bind=db_test.bind, tables=[ServerDefaultModel.__table__])

    record = ServerDefaultModel()
    db_test.add(record)
    db_test.flush()
    db_test.refresh(record)

    assert record.status == 'pending'
