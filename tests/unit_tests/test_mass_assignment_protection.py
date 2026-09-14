"""update_from_dict() のアローリスト方式と to_dict() の機密フィールド除外をテスト

repom#128: update_from_dict はホワイトリスト（updatable_fields /
allowed_fields）を必須とし、主キーとシステムカラムは allowed_fields に
含めても常に除外する。to_dict は sensitive_fields で機密カラムを除外できる。
"""
import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.models.base_model import BaseModel
from repom.mixins import SoftDeletableMixin


class AllowlistedModel(BaseModel):
    """updatable_fields を設定したテスト用モデル"""
    __tablename__ = 'allowlisted_model_mass_assignment'
    updatable_fields = {'name'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)


class NoAllowlistModel(BaseModel):
    """updatable_fields を設定していないテスト用モデル"""
    __tablename__ = 'no_allowlist_model_mass_assignment'

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class CustomPrimaryKeyModel(BaseModel, use_id=False):
    """id 以外の名前の主キーを持つテスト用モデル"""
    __tablename__ = 'custom_pk_model_mass_assignment'
    updatable_fields = {'uuid', 'name'}

    uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class SoftDeletableAllowlistModel(BaseModel, SoftDeletableMixin):
    """deleted_at を持つテスト用モデル"""
    __tablename__ = 'soft_deletable_allowlist_model_mass_assignment'
    updatable_fields = {'name', 'deleted_at'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class SensitiveFieldModel(BaseModel):
    """sensitive_fields を設定したテスト用モデル"""
    __tablename__ = 'sensitive_field_model_mass_assignment'
    sensitive_fields = {'password_hash'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False, default='hashed')


def test_update_from_dict_rejects_unlisted_field(db_test):
    """updatable_fields にないフィールドは無視され、返り値は許可フィールドの変更有無のみを反映する"""
    model = AllowlistedModel(name='original', is_admin=False)
    db_test.add(model)
    db_test.commit()

    result = model.update_from_dict({'is_admin': True})
    db_test.commit()

    assert model.is_admin is False
    assert result is False


def test_update_from_dict_requires_explicit_allowlist(db_test):
    """updatable_fields も allowed_fields も指定しない場合は ValueError"""
    model = NoAllowlistModel(name='original')
    db_test.add(model)
    db_test.commit()

    with pytest.raises(ValueError):
        model.update_from_dict({'name': 'updated'})


def test_update_from_dict_excludes_all_primary_keys(db_test):
    """id 以外の名前の主キー（uuid）も allowed_fields に含めて更新不可"""
    model = CustomPrimaryKeyModel(uuid='11111111-1111-1111-1111-111111111111', name='original')
    db_test.add(model)
    db_test.commit()
    original_uuid = model.uuid

    model.update_from_dict({'uuid': '22222222-2222-2222-2222-222222222222', 'name': 'updated'})
    db_test.commit()

    assert model.uuid == original_uuid
    assert model.name == 'updated'


def test_update_from_dict_excludes_deleted_at(db_test):
    """deleted_at を allowed_fields に含めても un-delete はできない"""
    model = SoftDeletableAllowlistModel(name='original')
    db_test.add(model)
    db_test.commit()
    assert model.deleted_at is None

    model.update_from_dict({'deleted_at': '2020-01-01T00:00:00+00:00', 'name': 'updated'})
    db_test.commit()

    assert model.deleted_at is None
    assert model.name == 'updated'


def test_to_dict_omits_sensitive_fields(db_test):
    """sensitive_fields に列挙したカラムは to_dict() の結果に含まれない"""
    model = SensitiveFieldModel(name='original', password_hash='secret')
    db_test.add(model)
    db_test.commit()

    data = model.to_dict()

    assert 'password_hash' not in data
    assert data['name'] == 'original'
