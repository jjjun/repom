"""
create_test_fixtures を使ったマルチスレッドアクセステスト

このテストは、実際のテストで使用される create_test_fixtures が
engine_kwargs を正しく適用しているかを検証する。

修正前：create_test_fixtures は engine_kwargs を渡していないため、
        StaticPool が適用されず、マルチスレッドでエラーが発生する。

修正後：create_test_fixtures が engine_kwargs を渡すことで、
        StaticPool が適用され、マルチスレッドでも正常に動作する。
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from repom.base_model import BaseModel
from repom.testing import create_test_fixtures

# CRITICAL: モジュールレベルで create_test_fixtures を呼び出す前に
# EXEC_ENV を設定しないと、conftest.py が実行される前に
# db.dev.sqlite3 (ファイルベース) が使用されてしまう
os.environ['EXEC_ENV'] = 'test'


class FixtureTestModel(BaseModel):
    """create_test_fixtures を使ったテスト用モデル"""

    __tablename__ = "fixture_test"

    name: Mapped[str] = mapped_column(String(100))


# create_test_fixtures を使って fixture を作成
# この時点で EXEC_ENV='test' なので :memory: DB が使用される
db_engine, db_test = create_test_fixtures()


class TestCreateTestFixturesMultithread:
    """
    create_test_fixtures を使ったマルチスレッドテスト

    実際のテストで使われる create_test_fixtures が
    マルチスレッド環境で正しく動作することを検証する。
    """

    def test_multithread_read_with_fixtures(self, db_test):
        """
        create_test_fixtures を使った複数スレッドからの読み取りテスト

        このテストが成功する条件：
        - create_test_fixtures が engine_kwargs を渡している
        - engine_kwargs に StaticPool が設定されている
        - 複数スレッドから :memory: DB のデータが見える
        """
        # テストデータを投入
        for i in range(5):
            item = FixtureTestModel(name=f"fixture_item_{i}")
            db_test.add(item)
        db_test.commit()

        thread_ids = set()
        results = []

        def read_from_db(thread_num: int):
            """別スレッドから DB を読み取る"""
            time.sleep(0.01 * thread_num)  # 並列実行を確保
            thread_id = threading.get_ident()
            thread_ids.add(thread_id)

            # db_test を使って読み取り
            stmt = select(FixtureTestModel).where(
                FixtureTestModel.name == f"fixture_item_{thread_num}"
            )
            item = db_test.execute(stmt).scalar_one()
            return {"thread": thread_id, "name": item.name, "id": item.id}

        # 複数スレッドで同時にアクセス
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(read_from_db, i) for i in range(5)]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        # 検証
        assert len(results) == 5
        assert len(thread_ids) > 1, "複数のスレッドから実行されるべき"

        # すべてのアイテムが正しく読み取れたことを確認
        names = {r["name"] for r in results}
        assert names == {f"fixture_item_{i}" for i in range(5)}

    def test_multithread_write_with_fixtures(self, db_test):
        """
        create_test_fixtures を使った複数スレッドからの書き込みテスト

        このテストが成功する条件：
        - create_test_fixtures が engine_kwargs を渡している
        - StaticPool により単一接続が共有されている
        - 複数スレッドからの書き込みが同じ DB に反映される
        """
        thread_ids = set()

        def write_to_db(item_num: int):
            """別スレッドから DB に書き込む"""
            time.sleep(0.01 * item_num)  # 並列実行を確保
            thread_id = threading.get_ident()
            thread_ids.add(thread_id)

            # db_test を使って書き込み
            new_item = FixtureTestModel(name=f"fixture_new_{item_num}")
            db_test.add(new_item)
            db_test.commit()
            db_test.refresh(new_item)
            return {"thread": thread_id, "id": new_item.id}

        # 複数スレッドで同時に書き込み
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(write_to_db, i) for i in range(3)]
            results = [f.result() for f in as_completed(futures)]

        # 検証
        assert len(results) == 3
        assert len(thread_ids) > 1, "複数のスレッドから実行されるべき"

        # 書き込みが成功したことを確認
        stmt = select(FixtureTestModel).where(
            FixtureTestModel.name.like("fixture_new_%")
        )
        new_items = db_test.execute(stmt).scalars().all()
        assert len(new_items) == 3


class TestCreateTestFixturesConfiguration:
    """
    create_test_fixtures の設定テスト

    engine_kwargs が正しく適用されているかを検証する。
    """

    def test_engine_uses_static_pool(self, db_engine):
        """
        create_test_fixtures で作成された engine が StaticPool を使用していることを確認

        修正前：NullPool (default) が使用される
        修正後：StaticPool が使用される
        """
        # engine の pool class を確認
        pool = db_engine.pool
        from sqlalchemy.pool import StaticPool

        # StaticPool が使用されていることを確認
        assert isinstance(
            pool, StaticPool
        ), f"Expected StaticPool, got {type(pool).__name__}"

    def test_check_same_thread_is_disabled(self, db_engine):
        """
        check_same_thread が無効化されていることを確認

        StaticPool と組み合わせることで、マルチスレッドアクセスが可能になる。
        """
        # connect_args を確認
        connect_args = db_engine.url.query.get("check_same_thread")

        # URL に含まれていない場合は、engine 作成時の connect_args を確認する必要がある
        # ここでは、実際に別スレッドからアクセスできることで検証する
        connection = db_engine.connect()

        def access_from_thread():
            # 別スレッドから同じ connection を使用
            # check_same_thread=False でないとエラーになる
            try:
                result = connection.execute(select(1))
                return result.scalar()
            except Exception as e:
                return str(e)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(access_from_thread)
            result = future.result()

        connection.close()

        # エラーが発生していないことを確認
        assert result == 1, f"Expected 1, got {result}"
