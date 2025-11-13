"""Tests for BaseModelAuto with use_id フラグ"""

from tests._init import *
from sqlalchemy import Column, String, Integer, Date, Time, inspect
from tests.db_test_fixtures import db_test
from repom.base_model_auto import BaseModelAuto


class AutoModelWithId(BaseModelAuto, use_id=True):
    """BaseModelAutoを継承し、use_id=True を明示的に指定したモデル"""
    __tablename__ = 'auto_model_with_id'

    name = Column(
        String(100),
        nullable=False,
        info={'description': '名前'}
    )
    age = Column(
        Integer,
        nullable=True,
        info={'description': '年齢'}
    )


class AutoModelWithoutId(BaseModelAuto):
    """BaseModelAutoを継承し、デフォルトの use_id=False を使用したモデル"""
    __tablename__ = 'auto_model_without_id'

    code = Column(
        String(50),
        primary_key=True,
        info={'description': 'コード'}
    )
    name = Column(
        String(100),
        nullable=False,
        info={'description': '名前'}
    )


class AutoModelWithCompositePK(BaseModelAuto):
    """BaseModelAutoを継承し、複合主キーを使用するモデル（use_id=False はデフォルト）"""
    __tablename__ = 'auto_model_with_composite_pk'

    date = Column(
        Date,
        primary_key=True,
        info={'description': '日付'}
    )
    time = Column(
        Time,
        primary_key=True,
        info={'description': '時刻'}
    )
    description = Column(
        String(255),
        nullable=True,
        info={'description': '説明'}
    )


# ========================================
# use_id=True のテスト
# ========================================

def test_auto_model_with_id_has_id_column():
    """BaseModelAutoでuse_id=Trueの場合、idカラムが存在することを確認"""
    mapper = inspect(AutoModelWithId)
    column_names = [col.key for col in mapper.columns]

    # idカラムが存在することを確認
    assert 'id' in column_names
    # 定義したカラムも存在することを確認
    assert 'name' in column_names
    assert 'age' in column_names


def test_auto_model_with_id_primary_key():
    """BaseModelAutoでuse_id=Trueの場合、idが主キーであることを確認"""
    mapper = inspect(AutoModelWithId)
    primary_keys = [col.name for col in mapper.primary_key]

    assert 'id' in primary_keys
    assert len(primary_keys) == 1


# ========================================
# use_id=False のテスト
# ========================================

def test_auto_model_without_id_has_no_id_column():
    """BaseModelAutoはデフォルトで use_id=False なので、idカラムが存在しないことを確認"""
    mapper = inspect(AutoModelWithoutId)
    column_names = [col.key for col in mapper.columns]

    # idカラムが存在しないことを確認
    assert 'id' not in column_names
    # 定義したカラムは存在することを確認
    assert 'code' in column_names
    assert 'name' in column_names


def test_auto_model_without_id_primary_key():
    """BaseModelAutoでuse_id=Falseの場合、指定したカラムが主キーになることを確認"""
    mapper = inspect(AutoModelWithoutId)
    primary_keys = [col.name for col in mapper.primary_key]

    assert 'code' in primary_keys
    assert 'id' not in primary_keys
    assert len(primary_keys) == 1


# ========================================
# 複合主キー（use_id=False）のテスト
# ========================================

def test_auto_model_with_composite_pk_has_no_id_column():
    """BaseModelAutoで複合主キーの場合、idカラムが存在しないことを確認"""
    mapper = inspect(AutoModelWithCompositePK)
    column_names = [col.key for col in mapper.columns]

    # idカラムが存在しないことを確認
    assert 'id' not in column_names
    # 複合主キーのカラムが存在することを確認
    assert 'date' in column_names
    assert 'time' in column_names
    assert 'description' in column_names


def test_auto_model_with_composite_pk_primary_keys():
    """BaseModelAutoで複合主キーが正しく設定されることを確認"""
    mapper = inspect(AutoModelWithCompositePK)
    primary_keys = [col.name for col in mapper.primary_key]

    # 複合主キーが正しく設定されていることを確認
    assert 'date' in primary_keys
    assert 'time' in primary_keys
    # idは含まれないことを確認
    assert 'id' not in primary_keys
    # 主キーが2つであることを確認
    assert len(primary_keys) == 2


def test_auto_model_with_composite_pk_database_structure(db_test):
    """BaseModelAutoで複合主キーのモデルがデータベースで正しく作成されることを確認"""
    from sqlalchemy import inspect as sqla_inspect
    from repom.db import engine

    # データベースのテーブル構造を確認
    inspector = sqla_inspect(engine)
    columns = inspector.get_columns('auto_model_with_composite_pk')
    column_names = [col['name'] for col in columns]

    # idカラムが存在しないことを確認
    assert 'id' not in column_names
    # 複合主キーのカラムが存在することを確認
    assert 'date' in column_names
    assert 'time' in column_names
    assert 'description' in column_names

    # 主キーの確認
    pk_constraint = inspector.get_pk_constraint('auto_model_with_composite_pk')
    pk_columns = pk_constraint['constrained_columns']
    assert 'date' in pk_columns
    assert 'time' in pk_columns
    assert 'id' not in pk_columns


# ========================================
# Column.info の継承確認
# ========================================

def test_auto_model_column_info():
    """BaseModelAutoでColumn.infoが正しく保持されていることを確認"""
    mapper = inspect(AutoModelWithId)

    # nameカラムのinfoを取得
    name_col = mapper.columns['name']
    assert name_col.info is not None
    assert name_col.info.get('description') == '名前'

    # ageカラムのinfoを取得
    age_col = mapper.columns['age']
    assert age_col.info is not None
    assert age_col.info.get('description') == '年齢'


# ========================================
# スキーマ生成テスト: get_create_schema
# ========================================

def test_create_schema_with_id():
    """use_id=Trueのモデルのcreateスキーマにidが含まれないことを確認"""
    CreateSchema = AutoModelWithId.get_create_schema()

    # スキーマのフィールドを取得
    fields = CreateSchema.model_fields

    # idは自動生成されるため、createスキーマには含まれない（システムカラムとして除外）
    assert 'id' not in fields
    # created_at, updated_at も自動生成されるため含まれない
    assert 'created_at' not in fields
    assert 'updated_at' not in fields
    # 定義したフィールドは含まれる
    assert 'name' in fields
    assert 'age' in fields


def test_create_schema_without_id():
    """use_id=Falseのモデルのcreateスキーマの確認"""
    CreateSchema = AutoModelWithoutId.get_create_schema()

    # スキーマのフィールドを取得
    fields = CreateSchema.model_fields

    # idカラムがないので、もちろん含まれない
    assert 'id' not in fields
    # 定義したフィールドは含まれる
    assert 'code' in fields
    assert 'name' in fields


def test_create_schema_with_composite_pk():
    """use_composite_pk=Trueのモデルのcreateスキーマの確認"""
    CreateSchema = AutoModelWithCompositePK.get_create_schema()

    # スキーマのフィールドを取得
    fields = CreateSchema.model_fields

    # idカラムがないので含まれない
    assert 'id' not in fields
    # created_at, updated_at は除外される
    assert 'created_at' not in fields
    assert 'updated_at' not in fields
    # 複合主キーのフィールドは含まれる
    assert 'date' in fields
    assert 'time' in fields
    assert 'description' in fields


# ========================================
# スキーマ生成テスト: get_update_schema
# ========================================

def test_update_schema_with_id():
    """use_id=Trueのモデルのupdateスキーマにidが含まれないことを確認"""
    UpdateSchema = AutoModelWithId.get_update_schema()

    # スキーマのフィールドを取得
    fields = UpdateSchema.model_fields

    # idは更新対象外のため含まれない（システムカラムとして除外）
    assert 'id' not in fields
    # created_at, updated_at も除外される
    assert 'created_at' not in fields
    assert 'updated_at' not in fields
    # 定義したフィールドは含まれる（すべてOptional）
    assert 'name' in fields
    assert 'age' in fields


def test_update_schema_without_id():
    """use_id=Falseのモデルのupdateスキーマの確認"""
    UpdateSchema = AutoModelWithoutId.get_update_schema()

    # スキーマのフィールドを取得
    fields = UpdateSchema.model_fields

    # idカラムがないので含まれない
    assert 'id' not in fields
    # 定義したフィールドは含まれる
    assert 'code' in fields
    assert 'name' in fields


def test_update_schema_with_composite_pk():
    """use_composite_pk=Trueのモデルのupdateスキーマの確認"""
    UpdateSchema = AutoModelWithCompositePK.get_update_schema()

    # スキーマのフィールドを取得
    fields = UpdateSchema.model_fields

    # idカラムがないので含まれない
    assert 'id' not in fields
    # created_at, updated_at は除外される
    assert 'created_at' not in fields
    assert 'updated_at' not in fields
    # 定義したフィールドは含まれる
    assert 'date' in fields
    assert 'time' in fields
    assert 'description' in fields


# ========================================
# スキーマのフィールド型確認
# ========================================

def test_schema_field_types():
    """生成されたスキーマのフィールド型が正しいことを確認"""
    CreateSchema = AutoModelWithId.get_create_schema()

    # nameは必須フィールド（nullable=False）
    name_field = CreateSchema.model_fields['name']
    assert name_field.is_required()

    # ageはオプショナル（nullable=True）
    age_field = CreateSchema.model_fields['age']
    assert not age_field.is_required()


def test_schema_field_descriptions():
    """生成されたスキーマのフィールドにdescriptionが含まれることを確認"""
    CreateSchema = AutoModelWithId.get_create_schema()

    # descriptionがフィールドメタデータに含まれていることを確認
    name_field = CreateSchema.model_fields['name']
    assert name_field.description == '名前'

    age_field = CreateSchema.model_fields['age']
    assert age_field.description == '年齢'
