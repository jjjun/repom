"""Integration tests configuration - PostgreSQL specific"""
import pytest
import os


# 統合テスト用の設定
# 親の conftest.py が EXEC_ENV='test' を設定しているため、そのまま使用
# PostgreSQL 統合テストは repom_test データベースに接続する


@pytest.fixture(scope='session', autouse=True)
def setup_postgres_tables():
    """
    PostgreSQL 統合テスト用のテーブルセットアップ

    config.db_type='postgres' の場合のみ実行される。
    """
    from repom.config import config

    if config.db_type != 'postgres':
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
