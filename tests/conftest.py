# fmt: off
import os
import pytest
import logging

os.environ['EXEC_ENV'] = 'test'

from repom.testing import create_test_fixtures, create_async_test_fixtures


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
def setup_repom_db_tables():
    """
    repom.db.engine と repom.async_session.async_engine にテーブルを作成
    
    test_session.py などが get_db_session() を使用する際、
    これらのengineを使用するため、テーブルが必要。
    
    Note: EXEC_ENV='test' が設定されているため、両engineは :memory: + StaticPool
    create_test_fixtures() が作成する db_engine と同じ :memory: DB を参照する。
    
    autouse=True により、全テスト実行前に自動的に実行される。
    """
    from repom.base_model import Base
    from repom.db import engine
    from repom.async_session import async_engine
    import asyncio
    
    # モデルをロード（テーブル定義を Base.metadata に登録）
    from repom.utility import load_models
    load_models()
    
    # 同期 engine にテーブル作成
    Base.metadata.create_all(bind=engine)
    
    # 非同期 engine にテーブル作成
    async def create_async_tables():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    asyncio.run(create_async_tables())
    
    yield
    
    # クリーンアップ（オプション）
    Base.metadata.drop_all(bind=engine)


# repom/testing.py のヘルパー関数を使用してフィクスチャを作成
# 同期版（既存）
db_engine, db_test = create_test_fixtures()

# async 版（新規）
async_db_engine, async_db_test = create_async_test_fixtures()
