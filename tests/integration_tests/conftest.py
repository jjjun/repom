"""Integration tests configuration - PostgreSQL specific"""
import pytest
import os


# 統合テスト用の設定
# conftest.py が EXEC_ENV='test' を設定するため、PostgreSQL 統合テスト用に 'dev' に変更
os.environ['EXEC_ENV'] = 'dev'


@pytest.fixture(scope='session', autouse=True)
def setup_postgres_tables():
    """
    PostgreSQL 統合テスト用のテーブルセットアップ
    
    DB_TYPE=postgres の場合のみ実行される。
    """
    db_type = os.getenv('DB_TYPE', 'sqlite')
    
    if db_type != 'postgres':
        # PostgreSQL 以外の場合は何もしない（親の conftest.py の fixture が実行される）
        return
    
    from repom.models.base_model import Base
    from repom.database import get_sync_engine
    from repom.utility import load_models
    
    # モデルをロード
    load_models()
    
    # 同期 engine にテーブル作成（PostgreSQL では非同期エンジンは不要）
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # テーブルをクリーンアップ（オプション）
    # Base.metadata.drop_all(bind=engine)
