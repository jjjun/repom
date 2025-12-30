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
    from repom.database import get_sync_engine, get_async_engine
    import asyncio

    # モデルをロード（テーブル定義を Base.metadata に登録）
    from repom.utility import load_models
    load_models()

    # Note: load_models() が既にテストモデルも含めてロードしているため、
    # 明示的なインポートは不要（重複定義エラーを避ける）

    # 同期 engine にテーブル作成
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)

    # 非同期 engine にテーブル作成
    async def create_async_tables():
        async_engine = await get_async_engine()
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


# ==================== Isolated Mapper Registry Fixture ====================

@pytest.fixture
def isolated_mapper_registry(db_test):
    """一時的なモデル定義用のフィクスチャ（改善版）

    一時的なモデルクラスを定義するテストで使用します。
    テスト終了後、自動的にマッパーをクリーンアップし、
    repom と behavior_tests の標準モデルを再構築します。

    使用例:
        def test_temporary_model(isolated_mapper_registry, db_test):
            from repom.base_model import BaseModel
            from sqlalchemy import String
            from sqlalchemy.orm import Mapped, mapped_column

            class TempModel(BaseModel):
                __tablename__ = 'temp_table'
                name: Mapped[str] = mapped_column(String(100))

            # テーブル作成
            BaseModel.metadata.create_all(bind=db_test.bind)

            # テスト実行
            # ...

    注意:
    - このフィクスチャを使うテストは他のテストに影響を与えません
    - clear_mappers() と再構築を自動的に行います
    - 一時的なモデルは BaseModel.metadata に登録されるため、
      テーブル作成には BaseModel.metadata.create_all() を使用してください
    - behavior_tests のモジュールレベルモデルも自動的に再ロードされます

    詳細: docs/guides/testing/isolated_mapper_fixture.md
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
    from repom.base_model import BaseModel
    from repom.database import Base
    import importlib
    import sys

    # テスト実行前の状態を保存（metadata のテーブル一覧）
    original_tables_base = set(Base.metadata.tables.keys())
    original_tables_repom = set(BaseModel.metadata.tables.keys())

    yield

    # クリーンアップ: 一時的なテーブルを削除
    temp_tables_base = set(Base.metadata.tables.keys()) - original_tables_base
    for table_name in list(temp_tables_base):  # list() でコピーを作成
        if table_name in Base.metadata.tables:
            Base.metadata.remove(Base.metadata.tables[table_name])

    temp_tables_repom = set(BaseModel.metadata.tables.keys()) - original_tables_repom
    for table_name in list(temp_tables_repom):  # list() でコピーを作成
        if table_name in BaseModel.metadata.tables:
            BaseModel.metadata.remove(BaseModel.metadata.tables[table_name])

    # マッパーをクリア（全マッパーがクリアされる）
    clear_mappers()

    # 【重要】behavior_tests のモジュールを再ロード
    # test_unique_key_handling はモジュールレベルでモデルを定義しているが、
    # このテストはフィクスチャを使わないので再ロードは不要
    # 代わりに、これらのモジュールは repom の load_models() で再構築される
    behavior_test_modules = [
        'tests.behavior_tests.test_date_type_comparison',
        'tests.behavior_tests.test_migration_no_id',
    ]

    # モジュールの再ロード前に、そのモジュールのテーブルを metadata から削除
    # これにより Table の再定義エラーを回避できる
    for module_name in behavior_test_modules:
        if module_name in sys.modules:
            try:
                # モジュール内のすべてのテーブルを削除
                module = sys.modules[module_name]
                for attr_name in dir(module):
                    try:
                        attr = getattr(module, attr_name)
                        if hasattr(attr, '__table__') and hasattr(attr.__table__, 'name'):
                            # このテーブルを metadata から削除
                            table_name = attr.__table__.name
                            if table_name in Base.metadata.tables:
                                Base.metadata.remove(Base.metadata.tables[table_name])
                            if table_name in BaseModel.metadata.tables:
                                BaseModel.metadata.remove(BaseModel.metadata.tables[table_name])
                    except Exception:
                        # 属性取得に失敗しても続行
                        pass

                # モジュールを再ロード
                importlib.reload(module)
            except Exception as e:
                # リロードに失敗しても続行（デバッグ用に警告を出力）
                import warnings
                warnings.warn(f"Failed to reload {module_name}: {e}")

    # repom の標準モデルを再ロード
    from repom.utility import load_models
    load_models()

    # マッパーを明示的に構築
    configure_mappers()

    # テーブルを再作成（db_test の engine に）
    Base.metadata.create_all(bind=db_test.bind)
    BaseModel.metadata.create_all(bind=db_test.bind)
