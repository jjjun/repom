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


@pytest.fixture(scope='session')
def setup_sqlite_tables():
    """
    SQLite専用: repom.db.engine と repom.async_session.async_engine にテーブルを作成

    test_session.py などが get_db_session() を使用する際、
    これらのengineを使用するため、テーブルが必要。

    Note: EXEC_ENV='test' が設定されているため、両engineは :memory: + StaticPool
    create_test_fixtures() が作成する db_engine と同じ :memory: DB を参照する。

    SQLiteの場合、同期・非同期両方のengineにテーブルを作成します。
    """
    from repom.models.base_model import Base
    from repom.database import get_sync_engine, get_async_engine
    import asyncio

    # モデルをロード（テーブル定義を Base.metadata に登録）
    from repom.utility import load_models
    load_models()

    # 同期 engine にテーブル作成
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)

    # 非同期 engine にテーブル作成（SQLiteは必要）
    async def create_async_tables():
        async_engine = await get_async_engine()
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_async_tables())

    yield

    # クリーンアップ
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope='session')
def setup_postgres_tables():
    """
    PostgreSQL専用: repom.db.engine にテーブルを作成

    PostgreSQL統合テスト用のテーブルセットアップ。
    非同期engineはパスワード認証問題のため作成しません。

    同期engineのみにテーブルを作成します。
    """
    from repom.models.base_model import Base
    from repom.database import get_sync_engine
    from repom.utility import load_models

    # モデルをロード
    load_models()

    # 同期 engine にテーブル作成（PostgreSQLは非同期不要）
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)

    yield

    # PostgreSQLはクリーンアップしない（データ永続化）
    # Base.metadata.drop_all(bind=engine)


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

