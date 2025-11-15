"""システムカラムの保護とupdated_atの自動更新をテスト"""
import pytest
from datetime import datetime
from time import sleep
from sqlalchemy import Column, String
from repom.base_model import BaseModel
from tests.db_test_fixtures import db_test


class SystemProtectionModel(BaseModel):
    """テスト用モデル（id, created_at, updated_at を持つ）"""
    __tablename__ = 'system_protection_model'
    use_created_at = True
    use_updated_at = True

    name = Column(String(100), nullable=False)


@pytest.fixture
def sample_model(db_test):
    """テスト用のモデルインスタンスを作成"""
    model = SystemProtectionModel(name='original')
    db_test.add(model)
    db_test.commit()
    return model


def test_update_from_dict_excludes_id(db_test, sample_model):
    """update_from_dict() で id が更新されないことを確認"""
    original_id = sample_model.id

    # id を含むデータで更新を試みる
    sample_model.update_from_dict({'id': 999, 'name': 'updated'})
    db_test.commit()

    # id は変更されていない
    assert sample_model.id == original_id
    # name は更新されている
    assert sample_model.name == 'updated'


def test_update_from_dict_excludes_created_at(db_test, sample_model):
    """update_from_dict() で created_at が更新されないことを確認"""
    original_created_at = sample_model.created_at

    # created_at を含むデータで更新を試みる
    new_time = datetime(2020, 1, 1)
    sample_model.update_from_dict({'created_at': new_time, 'name': 'updated'})
    db_test.commit()

    # created_at は変更されていない
    assert sample_model.created_at == original_created_at
    # name は更新されている
    assert sample_model.name == 'updated'


def test_update_from_dict_excludes_updated_at(db_test, sample_model):
    """update_from_dict() で updated_at が更新されないことを確認（手動変更不可）"""
    original_updated_at = sample_model.updated_at

    # updated_at を含むデータで更新を試みる
    new_time = datetime(2020, 1, 1)
    sample_model.update_from_dict({'updated_at': new_time, 'name': 'updated'})
    db_test.commit()

    # updated_at は手動では変更されていない（自動更新のみ）
    assert sample_model.updated_at != new_time
    # name は更新されている
    assert sample_model.name == 'updated'


def test_updated_at_auto_update_on_commit(db_test, sample_model):
    """commit() 時に updated_at が自動更新されることを確認"""
    original_updated_at = sample_model.updated_at

    # 少し待機（時刻の差を確保）
    sleep(0.01)

    # name を更新
    sample_model.name = 'updated'
    db_test.commit()

    # updated_at が自動更新されている
    assert sample_model.updated_at > original_updated_at


def test_created_at_not_change_on_update(db_test, sample_model):
    """更新時に created_at が変更されないことを確認"""
    original_created_at = sample_model.created_at

    # name を更新
    sample_model.name = 'updated'
    db_test.commit()

    # created_at は変更されていない
    assert sample_model.created_at == original_created_at


def test_all_system_columns_protected_together(db_test, sample_model):
    """全てのシステムカラムが同時に保護されることを確認"""
    original_id = sample_model.id
    original_created_at = sample_model.created_at
    original_updated_at = sample_model.updated_at

    # 少し待機（時刻の差を確保）
    sleep(0.01)

    # 全てのシステムカラムを含むデータで更新を試みる
    sample_model.update_from_dict({
        'id': 999,
        'created_at': datetime(2020, 1, 1),
        'updated_at': datetime(2020, 1, 1),
        'name': 'updated'
    })
    db_test.commit()

    # システムカラムは全て保護されている
    assert sample_model.id == original_id
    assert sample_model.created_at == original_created_at
    # updated_at は自動更新される（手動指定は無視）
    assert sample_model.updated_at > original_updated_at
    # 通常フィールドは更新される
    assert sample_model.name == 'updated'
