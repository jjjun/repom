"""BaseModelAuto の Response スキーマ生成機能をテスト"""
import pytest
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from repom.base_model_auto import BaseModelAuto
from tests.db_test_fixtures import db_test


class ResponseTestModel(BaseModelAuto):
    """Response スキーマテスト用モデル"""
    __tablename__ = 'response_test_model'
    use_created_at = True
    use_updated_at = True

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('categories.id'), nullable=True)


class CategoryModel(BaseModelAuto):
    """外部キー参照用のカテゴリモデル"""
    __tablename__ = 'categories'

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class SensitiveFKModel(BaseModelAuto):
    """センシティブな外部キーを持つモデル"""
    __tablename__ = 'sensitive_fk_model'

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 通常の外部キー（Create/Update に含まれる）
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('categories.id'), nullable=True)

    # センシティブな外部キー（Create/Update から除外）
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('users.id'),
        info={
            'in_create': False,
            'in_update': False,
            'description': '所有者ID（システム設定）'
        }
    )


class UserModel(BaseModelAuto):
    """外部キー参照用のユーザーモデル"""
    __tablename__ = 'users'

    username: Mapped[str] = mapped_column(String(100), nullable=False)


class ExplicitExcludeModel(BaseModelAuto):
    """明示的に Response から除外するフィールドを持つモデル"""
    __tablename__ = 'explicit_exclude_model'

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Response から明示的に除外
    password_hash: Mapped[str] = mapped_column(
        String(255),
        info={
            'in_response': False,
            'description': 'パスワードハッシュ（非公開）'
        }
    )


def test_response_schema_includes_system_columns(db_test):
    """Response スキーマに id, created_at, updated_at が含まれることを確認"""
    ResponseSchema = ResponseTestModel.get_response_schema()

    # システムカラムが含まれている
    assert 'id' in ResponseSchema.model_fields
    assert 'created_at' in ResponseSchema.model_fields
    assert 'updated_at' in ResponseSchema.model_fields


def test_response_schema_includes_regular_columns(db_test):
    """Response スキーマに通常カラムが含まれることを確認"""
    ResponseSchema = ResponseTestModel.get_response_schema()

    # 通常カラムが含まれている
    assert 'name' in ResponseSchema.model_fields
    assert 'email' in ResponseSchema.model_fields


def test_response_schema_includes_foreign_keys(db_test):
    """Response スキーマに外部キーが含まれることを確認"""
    ResponseSchema = ResponseTestModel.get_response_schema()

    # 外部キーが含まれている
    assert 'category_id' in ResponseSchema.model_fields


def test_response_schema_excludes_with_info_flag(db_test):
    """info={'in_response': False} で Response から除外されることを確認"""
    ResponseSchema = ExplicitExcludeModel.get_response_schema()

    # name は含まれる
    assert 'name' in ResponseSchema.model_fields
    # password_hash は除外される
    assert 'password_hash' not in ResponseSchema.model_fields


def test_response_field_decorator(db_test):
    """@response_field で宣言されたフィールドが Response に含まれることを確認"""
    class ModelWithResponseField(BaseModelAuto):
        __tablename__ = 'model_with_response_field'

        name: Mapped[str] = mapped_column(String(100), nullable=False)

        @BaseModelAuto.response_field(
            full_name=str,
            count=int
        )
        def to_dict(self):
            data = super().to_dict()
            data['full_name'] = f"{self.name} (Full)"
            data['count'] = 42
            return data

    ResponseSchema = ModelWithResponseField.get_response_schema()

    # カラムフィールド
    assert 'name' in ResponseSchema.model_fields
    # @response_field で宣言されたフィールド
    assert 'full_name' in ResponseSchema.model_fields
    assert 'count' in ResponseSchema.model_fields


def test_response_schema_default_behavior(db_test):
    """info を指定しない場合のデフォルト動作を確認"""
    class DefaultBehaviorModel(BaseModelAuto):
        __tablename__ = 'default_behavior_model'
        use_created_at = True
        use_updated_at = True

        # info なし → デフォルトで Response に含まれる
        name: Mapped[str] = mapped_column(String(100), nullable=False)
        category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('categories.id'), nullable=True)

    ResponseSchema = DefaultBehaviorModel.get_response_schema()

    # システムカラムが含まれる
    assert 'id' in ResponseSchema.model_fields
    assert 'created_at' in ResponseSchema.model_fields
    assert 'updated_at' in ResponseSchema.model_fields
    # 通常カラムが含まれる
    assert 'name' in ResponseSchema.model_fields
    # 外部キーが含まれる
    assert 'category_id' in ResponseSchema.model_fields


def test_create_schema_excludes_system_columns(db_test):
    """Create スキーマに id, created_at, updated_at が含まれないことを確認"""
    CreateSchema = ResponseTestModel.get_create_schema()

    # システムカラムは除外される
    assert 'id' not in CreateSchema.model_fields
    assert 'created_at' not in CreateSchema.model_fields
    assert 'updated_at' not in CreateSchema.model_fields

    # 通常カラムは含まれる
    assert 'name' in CreateSchema.model_fields
    assert 'email' in CreateSchema.model_fields
    # 外部キーは含まれる（デフォルト）
    assert 'category_id' in CreateSchema.model_fields


def test_update_schema_excludes_system_columns(db_test):
    """Update スキーマに id, created_at, updated_at が含まれないことを確認"""
    UpdateSchema = ResponseTestModel.get_update_schema()

    # システムカラムは除外される
    assert 'id' not in UpdateSchema.model_fields
    assert 'created_at' not in UpdateSchema.model_fields
    assert 'updated_at' not in UpdateSchema.model_fields

    # 通常カラムは含まれる
    assert 'name' in UpdateSchema.model_fields
    assert 'email' in UpdateSchema.model_fields
    # 外部キーは含まれる（デフォルト）
    assert 'category_id' in UpdateSchema.model_fields


def test_foreign_key_included_in_create_by_default(db_test):
    """外部キーがデフォルトで Create スキーマに含まれることを確認"""
    CreateSchema = SensitiveFKModel.get_create_schema()

    # 通常の外部キーは含まれる
    assert 'category_id' in CreateSchema.model_fields
    # センシティブな外部キー（info={'in_create': False}）は除外される
    assert 'owner_id' not in CreateSchema.model_fields


def test_foreign_key_included_in_update_by_default(db_test):
    """外部キーがデフォルトで Update スキーマに含まれることを確認"""
    UpdateSchema = SensitiveFKModel.get_update_schema()

    # 通常の外部キーは含まれる
    assert 'category_id' in UpdateSchema.model_fields
    # センシティブな外部キー（info={'in_update': False}）は除外される
    assert 'owner_id' not in UpdateSchema.model_fields


def test_foreign_key_included_in_response(db_test):
    """外部キーが Response スキーマに含まれることを確認"""
    ResponseSchema = SensitiveFKModel.get_response_schema()

    # 通常の外部キーは含まれる
    assert 'category_id' in ResponseSchema.model_fields
    # センシティブな外部キー（in_response 未指定）は Response に含まれる
    assert 'owner_id' in ResponseSchema.model_fields


def test_sensitive_foreign_key_excluded_from_create_update(db_test):
    """センシティブな外部キーが Create/Update から除外されることを確認"""
    CreateSchema = SensitiveFKModel.get_create_schema()
    UpdateSchema = SensitiveFKModel.get_update_schema()
    ResponseSchema = SensitiveFKModel.get_response_schema()

    # Create と Update からは除外される
    assert 'owner_id' not in CreateSchema.model_fields
    assert 'owner_id' not in UpdateSchema.model_fields
    # Response には含まれる（読み取り可能）
    assert 'owner_id' in ResponseSchema.model_fields


def test_response_schema_caching(db_test):
    """Response スキーマがキャッシュされることを確認"""
    schema1 = ResponseTestModel.get_response_schema()
    schema2 = ResponseTestModel.get_response_schema()

    # 同じインスタンスが返される（キャッシュが効いている）
    assert schema1 is schema2


def test_response_schema_can_validate_dict(db_test):
    """生成された Response スキーマで辞書をバリデーションできることを確認"""
    ResponseSchema = ResponseTestModel.get_response_schema()

    # バリデーション成功
    from datetime import datetime
    data = {
        'id': 1,
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'name': 'Test',
        'email': 'test@example.com',
        'category_id': 10
    }

    validated = ResponseSchema(**data)
    assert validated.id == 1
    assert validated.name == 'Test'
    assert validated.email == 'test@example.com'
    assert validated.category_id == 10
