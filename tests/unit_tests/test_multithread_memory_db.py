"""
マルチスレッド環境での :memory: DB アクセステスト

FastAPI の starlette.concurrency.run_in_threadpool を模倣して、
複数のスレッドから同時に in-memory SQLite DB にアクセスする。

StaticPool が正しく設定されていない場合、以下のエラーが発生する：
    sqlite3.ProgrammingError: SQLite objects created in a thread can only be
    used in that same thread. The object was created in thread id X and this
    is thread id Y.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel
from repom.config import RepomConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class MultithreadTestModel(BaseModel):
    """マルチスレッドテスト用モデル"""

    __tablename__ = "multithread_test"

    name: Mapped[str] = mapped_column(String(100))


class TestMultithreadMemoryDbAccess:
    """
    マルチスレッド環境での :memory: DB アクセステスト

    FastAPI の sync エンドポイントが run_in_threadpool で別スレッドで実行される
    シナリオを再現する。
    """

    @pytest.fixture(scope="function")
    def memory_engine(self, monkeypatch):
        """
        Test 環境用の :memory: DB エンジンを作成

        StaticPool が正しく設定されているかをテストするため、
        明示的に test 環境の設定を使用する。
        """
        # Test 環境の設定を使用
        monkeypatch.setenv("EXEC_ENV", "test")
        config = RepomConfig()
        config.exec_env = "test"  # 明示的に test 環境に設定
        # use_in_memory_db_for_tests が True であることを確認
        assert config.sqlite.use_in_memory_for_tests is True
        assert ":memory:" in config.db_url

        # エンジンを作成
        engine = create_engine(config.db_url, **config.engine_kwargs)

        # テーブルを作成
        BaseModel.metadata.create_all(engine)

        yield engine

    @pytest.fixture(scope="function")
    def seed_data(self, memory_engine):
        """テスト用データを投入"""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=memory_engine)
        session = SessionLocal()
        try:
            # テストデータを作成
            for i in range(5):
                item = MultithreadTestModel(name=f"item_{i}")
                session.add(item)
            session.commit()
        finally:
            session.close()

    def test_multithread_read_and_write_access(self, memory_engine, seed_data):
        """
        複数のスレッドから同時に読み取りアクセス

        FastAPI の sync エンドポイントが複数の worker スレッドで
        同時に実行されるシナリオを再現。
        """
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=memory_engine)
        start_together = threading.Barrier(3)
        connection_lock = threading.Lock()

        def read_and_write(item_num: int):
            start_together.wait()
            with connection_lock:
                session = SessionLocal()
                try:
                    new_item = MultithreadTestModel(name=f"new_item_{item_num}")
                    session.add(new_item)
                    session.commit()
                    session.refresh(new_item)

                    seeded_item = session.execute(
                        select(MultithreadTestModel).where(
                            MultithreadTestModel.name == f"item_{item_num}"
                        )
                    ).scalar_one()
                    return {
                        "thread": threading.get_ident(),
                        "new_item_id": new_item.id,
                        "seeded_name": seeded_item.name,
                    }
                finally:
                    session.close()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(read_and_write, i) for i in range(3)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 3
        assert len({result["thread"] for result in results}) == 3
        assert {result["seeded_name"] for result in results} == {
            "item_0",
            "item_1",
            "item_2",
        }
        assert all(result["new_item_id"] is not None for result in results)

        session = SessionLocal()
        try:
            new_items = session.execute(
                select(MultithreadTestModel).where(
                    MultithreadTestModel.name.like("new_item_%")
                )
            ).scalars().all()
            assert len(new_items) == 3
        finally:
            session.close()
