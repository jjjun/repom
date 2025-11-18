"""Tests for BaseModel UUID support

BaseModel の use_uuid=True パラメータによる UUID 主キーのサポートをテスト。

テスト内容:
- UUID の自動生成
- use_id と use_uuid の排他制御
- 外部キーとの互換性
- BaseRepository との互換性
- to_dict() メソッドの動作
- update_from_dict() での id 保護
"""

import uuid
import pytest
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model import BaseModel
from repom.base_repository import BaseRepository
from repom.db import Base


# ========================================
# Test Models
# ========================================

class UuidModel(BaseModel, use_uuid=True, use_created_at=True, use_updated_at=True):
    """UUID を主キーとして使用するモデル"""
    __tablename__ = 'uuid_models'
    
    name: Mapped[str] = mapped_column(String(100))


class IntIdModel(BaseModel, use_id=True):
    """従来の INTEGER id を使用するモデル"""
    __tablename__ = 'int_id_models'
    
    name: Mapped[str] = mapped_column(String(100))


class NoIdModel(BaseModel, use_id=False, use_uuid=False):
    """id を持たないモデル（複合主キー）"""
    __tablename__ = 'no_id_models'
    
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class RelatedModel(BaseModel, use_uuid=True):
    """外部キーで UuidModel を参照するモデル"""
    __tablename__ = 'related_models'
    
    uuid_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('uuid_models.id')
    )
    name: Mapped[str] = mapped_column(String(100))


# ========================================
# Repository for testing
# ========================================

class UuidModelRepository(BaseRepository[UuidModel]):
    pass


# ========================================
# Tests: UUID Generation
# ========================================

def test_uuid_model_creates_uuid_primary_key(db_test):
    """UUID モデルが UUID 主キーを自動生成すること"""
    model = UuidModel(name='Test')
    
    # id が自動生成されていること
    assert hasattr(model, 'id')
    assert isinstance(model.id, str)
    assert len(model.id) == 36  # UUID v4 format: 8-4-4-4-12 = 36 chars


def test_uuid_model_id_is_varchar_36(db_test):
    """UUID モデルの id カラムが VARCHAR(36) であること"""
    # テーブル定義を確認
    table = Base.metadata.tables['uuid_models']
    id_column = table.c.id
    
    assert id_column.primary_key
    assert str(id_column.type) == 'VARCHAR(36)'


def test_uuid_model_saves_to_database(db_test):
    """UUID モデルがデータベースに保存できること"""
    model = UuidModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    # データベースから取得
    retrieved = db_test.query(UuidModel).filter_by(name='Test').first()
    assert retrieved is not None
    assert retrieved.id == model.id
    assert isinstance(retrieved.id, str)


def test_uuid_is_unique_for_each_instance():
    """各インスタンスが異なる UUID を持つこと"""
    model1 = UuidModel(name='Test1')
    model2 = UuidModel(name='Test2')
    model3 = UuidModel(name='Test3')
    
    # 全て異なる UUID
    assert model1.id != model2.id
    assert model2.id != model3.id
    assert model1.id != model3.id


# ========================================
# Tests: use_id and use_uuid Mutual Exclusion
# ========================================

def test_use_id_and_use_uuid_are_mutually_exclusive():
    """use_id と use_uuid が排他的であること"""
    with pytest.raises(ValueError, match='use_id と use_uuid は同時に True にできません'):
        class InvalidModel(BaseModel, use_id=True, use_uuid=True):
            __tablename__ = 'invalid_model'


def test_int_id_model_has_integer_id(db_test):
    """use_id=True の場合、従来通り INTEGER id が作成されること"""
    model = IntIdModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    assert hasattr(model, 'id')
    assert isinstance(model.id, int)
    assert model.id >= 1


def test_no_id_model_has_no_id_column():
    """use_id=False, use_uuid=False の場合、id が作成されないこと"""
    model = NoIdModel(code='TEST', name='Test')
    
    assert not hasattr(model, 'id')
    assert hasattr(model, 'code')


# ========================================
# Tests: Foreign Key Compatibility
# ========================================

def test_foreign_key_references_uuid_id(db_test):
    """外部キーが UUID id を正しく参照すること"""
    # 親モデル作成
    parent = UuidModel(name='Parent')
    db_test.add(parent)
    db_test.commit()
    
    # 子モデル作成
    child = RelatedModel(uuid_model_id=parent.id, name='Child')
    db_test.add(child)
    db_test.commit()
    
    # 外部キーが正しく機能していること
    retrieved_child = db_test.query(RelatedModel).filter_by(name='Child').first()
    assert retrieved_child is not None
    assert retrieved_child.uuid_model_id == parent.id


# ========================================
# Tests: BaseRepository Compatibility
# ========================================

def test_repository_get_by_id_works_with_uuid(db_test):
    """BaseRepository の get_by_id() が UUID で動作すること"""
    # データ作成
    model = UuidModel(name='Test User')
    db_test.add(model)
    db_test.commit()
    uuid_id = model.id
    
    # Repository で取得（セッションを渡す）
    repo = UuidModelRepository(UuidModel, session=db_test)
    retrieved = repo.get_by_id(uuid_id)
    
    assert retrieved is not None
    assert retrieved.id == uuid_id
    assert retrieved.name == 'Test User'


def test_repository_create_works_with_uuid(db_test):
    """BaseRepository が UUID モデルで動作すること"""
    model = UuidModel(name='New User')
    db_test.add(model)
    db_test.commit()
    
    # Repository で取得できること
    repo = UuidModelRepository(UuidModel, session=db_test)
    retrieved = repo.get_by_id(model.id)
    
    assert retrieved is not None
    assert retrieved.id == model.id
    assert isinstance(retrieved.id, str)
    assert len(retrieved.id) == 36


def test_repository_get_by_works_with_uuid(db_test):
    """BaseRepository の get_by() が UUID モデルで動作すること"""
    # データ作成
    model1 = UuidModel(name='Alice')
    model2 = UuidModel(name='Bob')
    db_test.add_all([model1, model2])
    db_test.commit()
    
    # Repository で検索（セッションを渡す、位置引数形式）
    repo = UuidModelRepository(UuidModel, session=db_test)
    results = repo.get_by('name', 'Alice')
    
    assert len(results) == 1
    assert results[0].name == 'Alice'
    assert isinstance(results[0].id, str)


# ========================================
# Tests: to_dict() and update_from_dict()
# ========================================

def test_to_dict_includes_uuid_id(db_test):
    """to_dict() が UUID の id を含むこと"""
    model = UuidModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    data = model.to_dict()
    assert 'id' in data
    assert data['id'] == model.id
    assert isinstance(data['id'], str)


def test_update_from_dict_protects_uuid_id(db_test):
    """update_from_dict() が UUID id の変更を防ぐこと"""
    model = UuidModel(name='Original')
    db_test.add(model)
    db_test.commit()
    original_id = model.id
    
    # id を変更しようとする
    model.update_from_dict({'id': str(uuid.uuid4()), 'name': 'Updated'})
    db_test.commit()
    
    # id は変更されていないこと
    assert model.id == original_id
    # name は変更されていること
    assert model.name == 'Updated'


# ========================================
# Tests: created_at and updated_at
# ========================================

def test_uuid_model_with_created_at(db_test):
    """UUID モデルが created_at を持つこと"""
    model = UuidModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    assert hasattr(model, 'created_at')
    assert model.created_at is not None


def test_uuid_model_with_updated_at(db_test):
    """UUID モデルが updated_at を持つこと"""
    model = UuidModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    assert hasattr(model, 'updated_at')
    assert model.updated_at is not None


# ========================================
# Tests: UUID Format
# ========================================

def test_uuid_format_is_valid():
    """生成される UUID が RFC 4122 準拠のフォーマットであること"""
    model = UuidModel(name='Test')
    
    # UUID フォーマット: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    # ハイフンを含めて 36 文字
    assert len(model.id) == 36
    assert model.id.count('-') == 4
    
    # uuid モジュールでパース可能
    parsed_uuid = uuid.UUID(model.id)
    assert str(parsed_uuid) == model.id


def test_uuid_version_is_4():
    """生成される UUID が version 4 (random) であること"""
    model = UuidModel(name='Test')
    parsed_uuid = uuid.UUID(model.id)
    
    # UUID version 4
    assert parsed_uuid.version == 4
