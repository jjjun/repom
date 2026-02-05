# fmt: off
import os
import pytest
import logging

os.environ['EXEC_ENV'] = 'test'

from repom.testing import create_test_fixtures, create_async_test_fixtures

# テストモデルをインポート（自動登録される）
from tests.fixtures.models import User, Post, Parent, Child


def pytest_configure(config):
    # -vv オプション時のみデバッグログを有効化
    if config.option.verbose >= 2:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('data/repom/logs/test.log', encoding='utf-8')
            ]
        )
        logging.getLogger('repom').setLevel(logging.DEBUG)
    else:
        # 通常のテスト実行時は WARNING レベル以上のみ
        logging.getLogger('repom').setLevel(logging.WARNING)

    # 外部ライブラリの詳細ログを抑制（常に WARNING 以上）
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


@pytest.fixture(scope='session', autouse=True)
def setup_database_tables():
    """
    データベースタイプに応じてテーブルを自動作成

    config.db_type に基づいて適切なセットアップを実行:
    - SQLite: 同期・非同期両方のengineにテーブル作成
    - PostgreSQL: 同期engineのみにテーブル作成

    autouse=True により、全テストで自動実行されます。
    """
    from repom.models.base_model import Base
    from repom.database import get_sync_engine, get_async_engine
    from repom.config import config
    from repom.utility import load_models
    import asyncio

    # モデルをロード（テーブル定義を Base.metadata に登録）
    load_models()

    # 同期 engine にテーブル作成
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)

    # SQLite の場合のみ非同期 engine にもテーブル作成
    if config.db_type == 'sqlite':
        async def create_async_tables():
            async_engine = await get_async_engine()
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(create_async_tables())

    yield

    # SQLite の場合のみクリーンアップ（PostgreSQL はデータ永続化）
    if config.db_type == 'sqlite':
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope='session', autouse=True)
def setup_test_models(db_engine):
    """テストモデルのテーブルを作成

    このフィクスチャは session スコープで自動実行され、
    tests/fixtures/models/ で定義されたモデルのテーブルを作成します。

    Transaction Rollback パターンと組み合わせることで:
    - テーブル作成は1回のみ（高速）
    - 各テストはトランザクションで分離
    - データは自動ロールバック

    Note: db_engine フィクスチャに依存しているため、
    db_engine の作成後に実行されます。
    """
    from repom.models.base_model import BaseModel

    # BaseModel.metadata には repom のモデル + テストモデルが含まれる
    BaseModel.metadata.create_all(bind=db_engine)
    yield
    # テスト終了後のクリーンアップ（セッション終了時）
    # Transaction Rollback パターンでは通常不要だが、念のため実行
    BaseModel.metadata.drop_all(bind=db_engine)


# repom/testing.py のヘルパー関数を使用してフィクスチャを作成
# 同期版（既存）
db_engine, db_test = create_test_fixtures()

# async 版（新規）
async_db_engine, async_db_test = create_async_test_fixtures()


# ==================== Test Cleanup ====================
# Tests that need mapper cleanup should use clear_mappers() and configure_mappers() directly.
# Example:
#   from sqlalchemy.orm import clear_mappers, configure_mappers
#   try:
#       # test code
#   finally:
#       clear_mappers()
#       configure_mappers()

