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


def test_server_default_with_nullable():
    """server_default と nullable=True の組み合わせが Optional として扱われることを確認"""
    class NullableServerDefaultModel(BaseModelAuto):
        __tablename__ = 'nullable_server_default_model'
        
        status: Mapped[Optional[str]] = mapped_column(
            String(50),
            nullable=True,
            server_default=text("'pending'")
        )
    
    CreateSchema = NullableServerDefaultModel.get_create_schema()
    status_field = CreateSchema.model_fields['status']
    
    assert not status_field.is_required()
    assert status_field.default is None
    assert status_field.annotation == Optional[str]


def test_server_default_with_client_default():
    """server_default と client-side default の両方がある場合"""
    class BothDefaultsModel(BaseModelAuto):
        __tablename__ = 'both_defaults_model'
        
        status: Mapped[str] = mapped_column(
            String(50),
            nullable=False,
            default='client_default',
            server_default=text("'server_default'")
        )
    
    CreateSchema = BothDefaultsModel.get_create_schema()
    status_field = CreateSchema.model_fields['status']
    
    # col.default が優先されるため、必須ではない
    assert not status_field.is_required()
    # client-side default が使われる
    assert status_field.default == 'client_default'


def test_server_default_with_explicit_required_override():
    """info={'create_required': True} で明示的に必須にオーバーライドできることを確認"""
    class ExplicitRequiredModel(BaseModelAuto):
        __tablename__ = 'explicit_required_model'
        
        status: Mapped[str] = mapped_column(
            String(50),
            nullable=False,
            server_default=text("'pending'"),
            info={'create_required': True, 'description': '明示的に必須'}
        )
    
    CreateSchema = ExplicitRequiredModel.get_create_schema()
    status_field = CreateSchema.model_fields['status']
    
    # info で明示的に必須としているため、Required
    assert status_field.is_required()
    assert status_field.annotation == str  # Optional ではない


def test_server_default_in_update_schema():
    """server_default が Update スキーマにも影響しないことを確認（全フィールド Optional）"""
    CreateSchema = ServerDefaultModel.get_create_schema()
    UpdateSchema = ServerDefaultModel.get_update_schema()
    
    # Create スキーマでは Optional
    create_field = CreateSchema.model_fields['status']
    assert not create_field.is_required()
    assert create_field.annotation == Optional[str]
    
    # Update スキーマでも Optional（全フィールド Optional が仕様）
    update_field = UpdateSchema.model_fields['status']
    assert not update_field.is_required()
    assert update_field.annotation == Optional[str]


def test_server_default_not_in_response_schema():
    """server_default は Response スキーマには影響しない（カラムは含まれる）"""
    ResponseSchema = ServerDefaultModel.get_response_schema()
    
    # Response スキーマにはカラムが含まれる
    assert 'status' in ResponseSchema.model_fields
    
    # nullable=False なので、Response では Optional ではない
    response_field = ResponseSchema.model_fields['status']
    assert response_field.annotation == str  # Optional[str] ではない
