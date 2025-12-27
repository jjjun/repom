"""Tests for BaseModelAuto.get_create_schema and server_default handling"""

from typing import Optional

from tests._init import *
from sqlalchemy import String, func, text
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


def _build_server_default_model(name: str, server_default):
    return type(
        f'TempServerDefaultModel_{name}',
        (BaseModelAuto,),
        {
            '__tablename__': f'server_default_model_{name}',
            '__annotations__': {'status': Mapped[str]},
            'status': mapped_column(
                String(50),
                nullable=False,
                server_default=server_default,
                info={'description': f'ステータス（{name}）'},
            ),
            '__doc__': f'server_default を持つテストモデル ({name})',
        },
    )


@pytest.mark.parametrize(
    'name,server_default',
    [
        ('literal', 'pending'),
        ('sql_text', text("'pending'")),
        ('callable', func.now()),
    ],
)
def test_create_schema_treats_server_default_as_optional(name, server_default):
    """server_default がある非NULLカラムが create スキーマで必須にならないことを確認"""
    Model = _build_server_default_model(name, server_default)

    CreateSchema = Model.get_create_schema()
    status_field = CreateSchema.model_fields['status']

    assert not status_field.is_required()
    assert status_field.default is None
    assert status_field.annotation == Optional[str]


def test_server_default_applied_without_payload(db_test):
    """DB サーバーデフォルトが適用され、API 入力とズレる可能性があることを確認"""
    Base.metadata.create_all(bind=db_test.bind, tables=[ServerDefaultModel.__table__])

    record = ServerDefaultModel()
    db_test.add(record)
    db_test.flush()
    db_test.refresh(record)

    assert record.status == 'pending'
