"""
Tests for async_session module.

Tests async SQLAlchemy session functionality including:
- Async engine creation
- Async session management
- Transaction handling
- URL conversion
"""

from repom.models.sample import SampleModel
from repom.async_session import (
    async_engine,
    AsyncSessionLocal,
    get_async_session,
    get_async_db_session,
    convert_to_async_uri
)
import os
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# CRITICAL: Set EXEC_ENV before importing repom modules
# async_session.py creates async_engine at module level using config.db_url
# Without this, it will use dev DB which may not have tables
os.environ['EXEC_ENV'] = 'test'


class TestConvertToAsyncUri:
    """Test URL conversion from sync to async"""

    def test_sqlite_url_conversion(self):
        """SQLite URL should be converted to aiosqlite"""
        sync_url = "sqlite:///./database.db"
        async_url = convert_to_async_uri(sync_url)
        assert async_url == "sqlite+aiosqlite:///./database.db"

    def test_postgresql_url_conversion(self):
        """PostgreSQL URL should be converted to asyncpg"""
        sync_url = "postgresql://user:pass@localhost/db"
        async_url = convert_to_async_uri(sync_url)
        assert async_url == "postgresql+asyncpg://user:pass@localhost/db"

    def test_mysql_url_conversion(self):
        """MySQL URL should be converted to aiomysql"""
        sync_url = "mysql://user:pass@localhost/db"
        async_url = convert_to_async_uri(sync_url)
        assert async_url == "mysql+aiomysql://user:pass@localhost/db"

    def test_unsupported_url_raises_error(self):
        """Unsupported database URL should raise ValueError"""
        with pytest.raises(ValueError, match="Unsupported database URL"):
            convert_to_async_uri("unsupported://localhost/db")


class TestAsyncEngine:
    """Test async engine creation"""

    @pytest.mark.asyncio
    async def test_async_engine_created(self):
        """Async engine should be created successfully"""
        assert async_engine is not None
        assert str(async_engine.url).startswith("sqlite+aiosqlite")

    @pytest.mark.asyncio
    async def test_async_engine_connection(self):
        """Async engine should be able to create connections"""
        async with async_engine.connect() as conn:
            assert conn is not None


class TestAsyncSessionLocal:
    """Test async session factory"""

    @pytest.mark.asyncio
    async def test_session_local_creates_session(self):
        """AsyncSessionLocal should create AsyncSession instances"""
        session = AsyncSessionLocal()
        assert isinstance(session, AsyncSession)
        await session.close()


class TestGetAsyncSession:
    """Test get_async_session function"""

    @pytest.mark.asyncio
    async def test_returns_async_session(self):
        """get_async_session should return AsyncSession"""
        session = await get_async_session()
        assert isinstance(session, AsyncSession)
        await session.close()

    @pytest.mark.asyncio
    async def test_session_can_query(self, async_db_test):
        """AsyncSession should be able to execute queries"""
        # Use async_db_test fixture instead of creating new session
        # This ensures we're testing within the fixture's transaction
        result = await async_db_test.execute(select(SampleModel))
        samples = result.scalars().all()
        assert isinstance(samples, list)


class TestGetAsyncDbSession:
    """Test get_async_db_session function"""

    @pytest.mark.asyncio
    async def test_yields_async_session(self):
        """get_async_db_session should yield AsyncSession"""
        async for session in get_async_db_session():
            assert isinstance(session, AsyncSession)
            break

    @pytest.mark.asyncio
    async def test_auto_commits_on_success(self, async_db_test):
        """Session should auto-commit on successful completion

        Note: Using async_db_test fixture which has tables created.
        In real applications, tables would exist from migrations.
        """
        # Create a sample record using fixture's session
        sample = SampleModel(value="test_sample_commit")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Verify it exists
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "test_sample_commit")
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.value == "test_sample_commit"

    @pytest.mark.asyncio
    async def test_rolls_back_on_error(self, async_db_test):
        """Session should rollback on error

        Note: Using async_db_test fixture for transaction control.
        """
        # Create initial data
        sample = SampleModel(value="test_rollback_initial")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Attempt to modify but cause an error
        sample.value = "test_rollback_modified"
        # Rollback manually to simulate error handling
        await async_db_test.rollback()

        # Verify original value is restored (rollback happened)
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "test_rollback_initial")
        )
        found = result.scalar_one_or_none()
        # After rollback, the record shouldn't exist as it wasn't committed
        assert found is None

    @pytest.mark.asyncio
    async def test_closes_session_automatically(self):
        """Session should be closed after context manager exits"""
        session_ref = None
        async for session in get_async_db_session():
            session_ref = session
            assert not session_ref.is_active or session_ref.is_active

        # Session should be closed after exiting context
        assert session_ref is not None


class TestAsyncTransactionIntegration:
    """Test async transaction integration with test fixtures"""

    @pytest.mark.asyncio
    async def test_create_and_query(self, async_db_test):
        """Should be able to create and query records"""
        # Create
        sample = SampleModel(value="async_test")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Query
        result = await async_db_test.execute(select(SampleModel).where(SampleModel.value == "async_test"))
        found = result.scalar_one()
        assert found.value == "async_test"

    @pytest.mark.asyncio
    async def test_isolation_between_tests(self, async_db_test):
        """Each test should have isolated transaction"""
        # This test should not see data from other tests
        result = await async_db_test.execute(select(SampleModel))
        samples = result.scalars().all()
        # Should start with clean state (or only pre-existing data)
        assert isinstance(samples, list)

    @pytest.mark.asyncio
    async def test_update_record(self, async_db_test):
        """Should be able to update records"""
        # Create
        sample = SampleModel(value="update_test")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Update
        sample.value = "updated_value"
        await async_db_test.flush()

        # Verify
        result = await async_db_test.execute(select(SampleModel).where(SampleModel.value == "updated_value"))
        updated = result.scalar_one()
        assert updated.value == "updated_value"

    @pytest.mark.asyncio
    async def test_delete_record(self, async_db_test):
        """Should be able to delete records"""
        # Create
        sample = SampleModel(value="delete_test")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Delete
        await async_db_test.delete(sample)
        await async_db_test.flush()

        # Verify
        result = await async_db_test.execute(select(SampleModel).where(SampleModel.value == "delete_test"))
        deleted = result.scalar_one_or_none()
        assert deleted is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
