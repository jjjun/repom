"""Tests for BaseModelAuto.response_field decorator and get_response_schema"""

from tests._init import *
from sqlalchemy import String, Integer, inspect
from sqlalchemy.orm import Mapped, mapped_column
from typing import List, Optional
from repom.base_model_auto import BaseModelAuto


class ResponseModelWithId(BaseModelAuto):
    """use_id=Trueのモデルで@response_fieldを使用"""
    __tablename__ = 'response_model_with_id'

    use_id = True

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def is_active(self) -> bool:
        """カスタムプロパティ"""
        return self.count > 0

    @BaseModelAuto.response_field(
        is_active=bool,
        total_count=int
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'is_active': self.is_active,
            'total_count': self.count * 2
        })
        return data


class ResponseModelWithoutId(BaseModelAuto):
    """use_id=Falseのモデルで@response_fieldを使用"""
    __tablename__ = 'response_model_without_id'

    use_id = False

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)

    @BaseModelAuto.response_field(
        doubled_value=int,
        code_upper=str
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'doubled_value': self.value * 2,
            'code_upper': self.code.upper() if self.code else ''
        })
        return data


# ========================================
# response_field デコレータのテスト
# ========================================

def test_response_field_metadata():
    """@response_fieldデコレータがメタデータを正しく保存することを確認"""
    # to_dictメソッドに_response_fieldsメタデータが付与されていることを確認
    to_dict_method = ResponseModelWithId.to_dict
    assert hasattr(to_dict_method, '_response_fields')

    response_fields = to_dict_method._response_fields
    assert 'is_active' in response_fields
    assert 'total_count' in response_fields
    assert response_fields['is_active'] == bool
    assert response_fields['total_count'] == int


def test_response_field_does_not_affect_to_dict():
    """@response_fieldデコレータがto_dict()の動作に影響しないことを確認"""
    model = ResponseModelWithId(name='test', count=5)
    data = model.to_dict()

    # 追加フィールドが含まれていることを確認
    assert 'is_active' in data
    assert 'total_count' in data
    assert data['is_active'] is True
    assert data['total_count'] == 10


# ========================================
# get_response_schema のテスト（use_id=True）
# ========================================

def test_response_schema_with_id_includes_columns():
    """use_id=TrueのモデルのresponseスキーマにSQLAlchemyカラムが含まれることを確認"""
    ResponseSchema = ResponseModelWithId.get_response_schema()

    fields = ResponseSchema.model_fields

    # SQLAlchemyカラムが含まれる
    assert 'id' in fields
    assert 'name' in fields
    assert 'count' in fields


def test_response_schema_with_id_includes_extra_fields():
    """use_id=Trueのモデルのresponseスキーマに@response_fieldの追加フィールドが含まれることを確認"""
    ResponseSchema = ResponseModelWithId.get_response_schema()

    fields = ResponseSchema.model_fields

    # @response_fieldで宣言した追加フィールドが含まれる
    assert 'is_active' in fields
    assert 'total_count' in fields


# ========================================
# get_response_schema のテスト（use_id=False）
# ========================================

def test_response_schema_without_id_no_id_field():
    """use_id=Falseのモデルのresponseスキーマにidが含まれないことを確認"""
    ResponseSchema = ResponseModelWithoutId.get_response_schema()

    fields = ResponseSchema.model_fields

    # idカラムが存在しない
    assert 'id' not in fields
    # 定義したカラムは含まれる
    assert 'code' in fields
    assert 'value' in fields


def test_response_schema_without_id_includes_extra_fields():
    """use_id=Falseのモデルのresponseスキーマに@response_fieldの追加フィールドが含まれることを確認"""
    ResponseSchema = ResponseModelWithoutId.get_response_schema()

    fields = ResponseSchema.model_fields

    # @response_fieldで宣言した追加フィールドが含まれる
    assert 'doubled_value' in fields
    assert 'code_upper' in fields


# ========================================
# スキーマ名のカスタマイズ
# ========================================

def test_response_schema_custom_name():
    """カスタムスキーマ名が正しく設定されることを確認"""
    CustomSchema = ResponseModelWithId.get_response_schema(schema_name='CustomResponse')

    assert CustomSchema.__name__ == 'CustomResponse'


def test_response_schema_default_name():
    """デフォルトのスキーマ名が正しく生成されることを確認"""
    DefaultSchema = ResponseModelWithId.get_response_schema()

    # デフォルトは {ModelName}Response（"Model"が削除される）
    # ResponseModelWithId → ResponseWithId → ResponseWithIdResponse
    assert DefaultSchema.__name__ == 'ResponseWithIdResponse'


# ========================================
# スキーマキャッシュのテスト
# ========================================

def test_response_schema_caching():
    """スキーマが正しくキャッシュされることを確認"""
    Schema1 = ResponseModelWithId.get_response_schema()
    Schema2 = ResponseModelWithId.get_response_schema()

    # 同じインスタンスが返される（キャッシュが機能）
    assert Schema1 is Schema2


def test_response_schema_different_names_different_cache():
    """異なるスキーマ名で異なるキャッシュエントリが作成されることを確認"""
    Schema1 = ResponseModelWithId.get_response_schema(schema_name='Schema1')
    Schema2 = ResponseModelWithId.get_response_schema(schema_name='Schema2')

    # 異なるインスタンスが返される
    assert Schema1 is not Schema2
    assert Schema1.__name__ == 'Schema1'
    assert Schema2.__name__ == 'Schema2'


# ========================================
# Pydantic スキーマのバリデーション
# ========================================

def test_response_schema_can_validate_dict():
    """生成されたスキーマがto_dict()の結果をバリデーションできることを確認"""
    ResponseSchema = ResponseModelWithId.get_response_schema()

    # モデルインスタンスを作成
    model = ResponseModelWithId(name='test', count=5)
    model.id = 1  # テスト用にIDを設定

    # to_dict()の結果をバリデーション
    data = model.to_dict()
    validated = ResponseSchema(**data)

    assert validated.id == 1
    assert validated.name == 'test'
    assert validated.count == 5
    assert validated.is_active is True
    assert validated.total_count == 10


def test_response_schema_without_id_can_validate_dict():
    """use_id=Falseのモデルのスキーマがto_dict()の結果をバリデーションできることを確認"""
    ResponseSchema = ResponseModelWithoutId.get_response_schema()

    model = ResponseModelWithoutId(code='ABC', value=10)

    data = model.to_dict()
    validated = ResponseSchema(**data)

    assert validated.code == 'ABC'
    assert validated.value == 10
    assert validated.doubled_value == 20
    assert validated.code_upper == 'ABC'


# ========================================
# デバッグ用メソッドのテスト
# ========================================

def test_get_extra_fields_debug():
    """get_extra_fields_debug()が正しい情報を返すことを確認"""
    extra_fields = ResponseModelWithId.get_extra_fields_debug()

    assert 'is_active' in extra_fields
    assert 'total_count' in extra_fields
    assert extra_fields['is_active'] == bool
    assert extra_fields['total_count'] == int
