"""async test fixtures のテスト

create_async_test_fixtures() によって作成される async_db_engine と
async_db_test フィクスチャの動作を検証します。

テストケース:
1. async Session が正しく返される
2. Transaction Rollback によるテスト分離
3. async CRUD 操作
4. FastAPI Users パターンの動作確認
"""

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model_auto import BaseModelAuto


# テスト用モデル
class AsyncTestUser(BaseModelAuto):
    """async テスト用ユーザーモデル"""
    __tablename__ = "async_test_users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)


class TestAsyncDbEngine:
    """async_db_engine フィクスチャのテスト"""

    @pytest.mark.asyncio
    async def test_engine_is_created(self, async_db_engine):
        """async engine が作成される"""
        from sqlalchemy.ext.asyncio import AsyncEngine
        assert async_db_engine is not None
        assert isinstance(async_db_engine, AsyncEngine)

    @pytest.mark.asyncio
    async def test_tables_are_created(self, async_db_engine):
        """テーブルが作成されている"""
        from sqlalchemy import inspect

        # テーブル情報を取得
        async with async_db_engine.connect() as conn:
            def get_table_names(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()

            table_names = await conn.run_sync(get_table_names)

        # async_test_users テーブルが存在する
        assert "async_test_users" in table_names


class TestAsyncDbTest:
    """async_db_test フィクスチャのテスト"""

    @pytest.mark.asyncio
    async def test_provides_async_session(self, async_db_test):
        """async Session を返す"""
        from sqlalchemy.ext.asyncio import AsyncSession
        assert async_db_test is not None
        assert isinstance(async_db_test, AsyncSession)

    @pytest.mark.asyncio
    async def test_can_add_and_query(self, async_db_test):
        """レコードを追加してクエリできる"""
        # ユーザーを作成
        user = AsyncTestUser(
            email="test@example.com",
            hashed_password="hashed123"
        )
        async_db_test.add(user)
        await async_db_test.flush()

        # クエリで取得
        stmt = select(AsyncTestUser).where(AsyncTestUser.email == "test@example.com")
        result = await async_db_test.execute(stmt)
        found_user = result.scalar_one_or_none()

        assert found_user is not None
        assert found_user.email == "test@example.com"
        assert found_user.hashed_password == "hashed123"


class TestTransactionRollback:
    """Transaction Rollback によるテスト分離"""

    @pytest.mark.asyncio
    async def test_first_test_adds_data(self, async_db_test):
        """最初のテストでデータを追加"""
        user = AsyncTestUser(
            email="rollback_test1@example.com",
            hashed_password="hash1"
        )
        async_db_test.add(user)
        await async_db_test.flush()
        # Note: flush() のみで commit しないため、トランザクション内に留まる
        # これは意図的な動作で、テスト終了時に自動ロールバックされる

        # データが存在することを確認
        stmt = select(AsyncTestUser).where(
            AsyncTestUser.email == "rollback_test1@example.com"
        )
        result = await async_db_test.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is not None

    @pytest.mark.asyncio
    async def test_second_test_data_is_rolled_back(self, async_db_test):
        """2番目のテストでは前のデータが残っていない"""
        # 前のテストのデータは存在しない
        stmt = select(AsyncTestUser).where(
            AsyncTestUser.email == "rollback_test1@example.com"
        )
        result = await async_db_test.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is None  # ロールバックされている

    @pytest.mark.asyncio
    async def test_third_test_also_clean(self, async_db_test):
        """3番目のテストもクリーンな状態"""
        # 全てのテストデータが残っていない
        stmt = select(AsyncTestUser)
        result = await async_db_test.execute(stmt)
        all_users = result.scalars().all()

        assert len(all_users) == 0


class TestCRUDOperations:
    """async での CRUD 操作テスト"""

    @pytest.mark.asyncio
    async def test_create(self, async_db_test):
        """Create 操作"""
        user = AsyncTestUser(
            email="crud_create@example.com",
            hashed_password="hash"
        )
        async_db_test.add(user)
        await async_db_test.flush()

        assert user.id is not None

    @pytest.mark.asyncio
    async def test_read(self, async_db_test):
        """Read 操作"""
        # データ作成
        user = AsyncTestUser(
            email="crud_read@example.com",
            hashed_password="hash"
        )
        async_db_test.add(user)
        await async_db_test.flush()
        user_id = user.id

        # 読み込み
        stmt = select(AsyncTestUser).where(AsyncTestUser.id == user_id)
        result = await async_db_test.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.id == user_id

    @pytest.mark.asyncio
    async def test_update(self, async_db_test):
        """Update 操作"""
        # データ作成
        user = AsyncTestUser(
            email="crud_update@example.com",
            hashed_password="hash_old"
        )
        async_db_test.add(user)
        await async_db_test.flush()
        user_id = user.id

        # 更新
        user.hashed_password = "hash_new"
        await async_db_test.flush()

        # 確認
        stmt = select(AsyncTestUser).where(AsyncTestUser.id == user_id)
        result = await async_db_test.execute(stmt)
        updated = result.scalar_one()

        assert updated.hashed_password == "hash_new"

    @pytest.mark.asyncio
    async def test_delete(self, async_db_test):
        """Delete 操作"""
        # データ作成
        user = AsyncTestUser(
            email="crud_delete@example.com",
            hashed_password="hash"
        )
        async_db_test.add(user)
        await async_db_test.flush()
        user_id = user.id

        # 削除
        await async_db_test.delete(user)
        await async_db_test.flush()

        # 確認
        stmt = select(AsyncTestUser).where(AsyncTestUser.id == user_id)
        result = await async_db_test.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is None


class TestFastAPIUsersPattern:
    """FastAPI Users パターンのテスト"""

    @pytest.mark.asyncio
    async def test_user_registration_pattern(self, async_db_test):
        """ユーザー登録パターン"""
        # FastAPI Users と同じパターンでユーザーを作成
        user = AsyncTestUser(
            email="fastapi_user@example.com",
            hashed_password="hashed_password_123"
        )
        async_db_test.add(user)
        await async_db_test.flush()

        # FastAPI Users と同じパターンで検索
        stmt = select(AsyncTestUser).where(
            AsyncTestUser.email == "fastapi_user@example.com"
        )
        result = await async_db_test.execute(stmt)
        found_user = result.scalar_one_or_none()

        assert found_user is not None
        assert found_user.email == "fastapi_user@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_pattern(self, async_db_test):
        """メールアドレスでユーザーを取得するパターン"""
        # 複数ユーザー作成
        users = [
            AsyncTestUser(email=f"user{i}@example.com", hashed_password="hash")
            for i in range(3)
        ]
        for user in users:
            async_db_test.add(user)
        await async_db_test.flush()

        # 特定のユーザーを取得
        stmt = select(AsyncTestUser).where(
            AsyncTestUser.email == "user1@example.com"
        )
        result = await async_db_test.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.email == "user1@example.com"

    @pytest.mark.asyncio
    async def test_user_not_found_pattern(self, async_db_test):
        """ユーザーが見つからないパターン"""
        stmt = select(AsyncTestUser).where(
            AsyncTestUser.email == "nonexistent@example.com"
        )
        result = await async_db_test.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is None


class TestMultipleQueries:
    """複数クエリのテスト"""

    @pytest.mark.asyncio
    async def test_multiple_inserts(self, async_db_test):
        """複数レコードの挿入"""
        users = [
            AsyncTestUser(email=f"multi{i}@example.com", hashed_password=f"hash{i}")
            for i in range(5)
        ]

        for user in users:
            async_db_test.add(user)
        await async_db_test.flush()

        # 全件取得
        stmt = select(AsyncTestUser)
        result = await async_db_test.execute(stmt)
        all_users = result.scalars().all()

        assert len(all_users) == 5

    @pytest.mark.asyncio
    async def test_filtered_query(self, async_db_test):
        """フィルタ付きクエリ"""
        # テストデータ作成
        users = [
            AsyncTestUser(email=f"filter{i}@example.com", hashed_password="common")
            for i in range(3)
        ]
        users.append(
            AsyncTestUser(email="different@example.com", hashed_password="unique")
        )

        for user in users:
            async_db_test.add(user)
        await async_db_test.flush()

        # フィルタクエリ
        stmt = select(AsyncTestUser).where(
            AsyncTestUser.hashed_password == "common"
        )
        result = await async_db_test.execute(stmt)
        filtered = result.scalars().all()

        assert len(filtered) == 3
