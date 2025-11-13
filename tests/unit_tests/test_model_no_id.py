"""Tests for BaseModel with use_id=False"""

from tests._init import *
from sqlalchemy import Column, String, inspect
from tests.db_test_fixtures import db_test
from repom.base_model import BaseModel


class ModelWithoutId(BaseModel):
    """use_id=Falseを指定したモデル"""
    __tablename__ = 'model_without_id'

    use_id = False  # IDカラムを使用しない

    name = Column(String(100), primary_key=True)  # 代わりにnameをプライマリキーに
    description = Column(String(255))


class ModelWithId(BaseModel):
    """デフォルト（use_id=True）のモデル"""
    __tablename__ = 'model_with_id'

    name = Column(String(100))


def test_model_without_id_has_no_id_column():
    """use_id=Falseの場合、idカラムが存在しないことを確認"""
    # モデルのカラム一覧を取得
    mapper = inspect(ModelWithoutId)
    column_names = [col.key for col in mapper.columns]

    # idカラムが存在しないことを確認
    assert 'id' not in column_names
    # 定義したカラムは存在することを確認
    assert 'name' in column_names
    assert 'description' in column_names


def test_model_with_id_has_id_column():
    """use_id=True（デフォルト）の場合、idカラムが存在することを確認"""
    mapper = inspect(ModelWithId)
    column_names = [col.key for col in mapper.columns]

    # idカラムが存在することを確認
    assert 'id' in column_names
    # 定義したカラムも存在することを確認
    assert 'name' in column_names


def test_model_without_id_primary_key():
    """use_id=Falseの場合、別のカラムがプライマリキーになることを確認"""
    mapper = inspect(ModelWithoutId)
    primary_keys = [col.key for col in mapper.primary_key]

    # nameがプライマリキーであることを確認
    assert 'name' in primary_keys
    # idはプライマリキーではない
    assert 'id' not in primary_keys


def test_model_without_id_in_database(db_test):
    """use_id=Falseのモデルがデータベースに正しく作成されることを確認"""
    # モデルのインスタンスを作成
    model = ModelWithoutId(name='test_name', description='test_description')
    db_test.add(model)
    db_test.commit()

    # データベースから取得
    retrieved = db_test.query(ModelWithoutId).filter_by(name='test_name').first()

    # データが正しく保存されていることを確認
    assert retrieved is not None
    assert retrieved.name == 'test_name'
    assert retrieved.description == 'test_description'

    # idカラムが存在しないことを確認
    assert not hasattr(retrieved, 'id')


def test_model_without_id_table_structure(db_test):
    """データベーステーブルにidカラムが存在しないことを確認"""
    from sqlalchemy import inspect as sqla_inspect
    from repom.db import engine

    inspector = sqla_inspect(engine)
    columns = inspector.get_columns('model_without_id')
    column_names = [col['name'] for col in columns]

    # idカラムが存在しないことを確認
    assert 'id' not in column_names
    # 定義したカラムは存在することを確認
    assert 'name' in column_names
    assert 'description' in column_names


def test_model_with_id_table_structure(db_test):
    """デフォルトモデルのテーブルにはidカラムが存在することを確認"""
    from sqlalchemy import inspect as sqla_inspect
    from repom.db import engine

    inspector = sqla_inspect(engine)
    columns = inspector.get_columns('model_with_id')
    column_names = [col['name'] for col in columns]

    # idカラムが存在することを確認
    assert 'id' in column_names
    assert 'name' in column_names


def test_model_without_id_to_dict():
    """use_id=Falseのモデルのto_dict()にidが含まれないことを確認"""
    model = ModelWithoutId(name='test', description='desc')
    data = model.to_dict()

    # idキーが存在しないことを確認
    assert 'id' not in data
    # 定義したキーは存在することを確認
    assert 'name' in data
    assert 'description' in data
    assert data['name'] == 'test'
    assert data['description'] == 'desc'


def test_model_with_id_to_dict():
    """デフォルトモデルのto_dict()にはidが含まれることを確認"""
    model = ModelWithId(name='test')
    # idは自動生成されないため、明示的にNoneまたは値を設定
    data = model.to_dict()

    # idキーが存在することを確認（値はNoneかもしれない）
    assert 'id' in data
    assert 'name' in data
