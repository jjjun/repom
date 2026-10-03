"""Sensitive fields are excluded from model serialization."""
import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel


class SensitiveFieldModel(BaseModel):
    __tablename__ = 'sensitive_field_model_mass_assignment'
    sensitive_fields = {'password_hash'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False, default='hashed')


class SerializableSensitiveFieldModel(BaseModel):
    __tablename__ = 'serializable_sensitive_field_model'
    sensitive_fields = {'password_hash'}
    serializable_fields = {'name', 'password_hash'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    private_note: Mapped[str] = mapped_column(String(200), nullable=False)


def test_to_dict_omits_sensitive_fields(db_test):
    model = SensitiveFieldModel(name='original', password_hash='secret')
    db_test.add(model)
    db_test.commit()

    data = model.to_dict()

    assert 'password_hash' not in data
    assert data['name'] == 'original'


def test_to_dict_uses_class_serializable_and_sensitive_fields():
    model = SerializableSensitiveFieldModel(
        name='original',
        password_hash='secret',
        private_note='private',
    )
    model.sensitive_fields = set()
    model.serializable_fields = {'name', 'password_hash', 'private_note'}

    assert model.to_dict() == {'name': 'original'}


@pytest.mark.parametrize(
    'field',
    ['sensitive_fields', 'serializable_fields', 'updatable_fields'],
)
def test_model_constructor_rejects_control_fields(field):
    with pytest.raises(TypeError, match='class-level model controls'):
        SensitiveFieldModel(
            name='original',
            password_hash='secret',
            **{field: set()},
        )
