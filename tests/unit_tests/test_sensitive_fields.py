"""Sensitive fields are excluded from model serialization."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel


class SensitiveFieldModel(BaseModel):
    __tablename__ = 'sensitive_field_model_mass_assignment'
    sensitive_fields = {'password_hash'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False, default='hashed')


def test_to_dict_omits_sensitive_fields(db_test):
    model = SensitiveFieldModel(name='original', password_hash='secret')
    db_test.add(model)
    db_test.commit()

    data = model.to_dict()

    assert 'password_hash' not in data
    assert data['name'] == 'original'
