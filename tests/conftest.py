import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from repom.db import Base
from repom.config import config, load_set_model_hook_function


def pytest_configure(config):
    os.environ['EXEC_ENV'] = 'test'
    # CONFIG_HOOK を空文字列にすると py-mine の設定フックが無効化される
    # つまりは、このパッケージ単体で動かしたい場合には、CONFIG_HOOK を空にする
    os.environ['CONFIG_HOOK'] = ''


@pytest.fixture(scope='session')
def db_engine():
    """
    セッション全体で共有されるデータベースエンジン

    - テストセッション開始時に1回だけDB作成
    - 全テスト終了後にクリーンアップ
    - エンジンとコネクションプールを共有することで高速化
    """
    # モデルをロード
    load_set_model_hook_function()

    # エンジン作成
    engine = create_engine(config.db_url)

    # テーブル作成（1回のみ）
    Base.metadata.create_all(bind=engine)

    yield engine

    # クリーンアップ
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_test(db_engine):
    """
    各テスト関数で独立したトランザクション環境を提供

    トランザクションロールバック方式により：
    - ✅ 高速（DB再作成不要、ロールバックのみ）
    - ✅ 完全な分離（各テストが独立したトランザクション内）
    - ✅ クリーンな状態（自動ロールバックで確実にリセット）

    動作の流れ:
    1. テスト開始: 新しいコネクションとトランザクション開始
    2. テスト実行: 独立したトランザクション内でデータ操作
    3. テスト終了: ロールバック → すべての変更が取り消される
    """
    # 新しいコネクションとトランザクション開始
    connection = db_engine.connect()
    transaction = connection.begin()

    # トランザクション内のセッション作成
    session = scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=connection)
    )

    yield session

    # クリーンアップ（確実にロールバック）
    session.close()
    # トランザクションがまだアクティブな場合のみロールバック
    if transaction.is_active:
        transaction.rollback()
    connection.close()
