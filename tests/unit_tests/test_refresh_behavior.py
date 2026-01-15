"""
Test to verify if refresh() is needed after commit for AutoDateTime fields.

This test verifies the claim in the mine-py issue document:
https://github.com/mine-py/docs/issues/repom_async_repository_refresh_issue.md
"""
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model import BaseModel
from repom.repositories import BaseRepository, AsyncBaseRepository


class RefreshTestModel(BaseModel, use_created_at=True, use_updated_at=True):
    """Test model with AutoDateTime fields"""
    __tablename__ = 'test_refresh_model'
    __table_args__ = {'extend_existing': True}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


@pytest.fixture
def refresh_repo(db_test):
    """Repository only - data created per test due to different patterns"""
    return BaseRepository(RefreshTestModel, session=db_test)


@pytest_asyncio.fixture
async def async_refresh_repo(async_db_test):
    """Async repository only - data created per test due to different patterns"""
    return AsyncBaseRepository(RefreshTestModel, session=async_db_test)


class TestRefreshBehaviorSync:
    """Test refresh behavior for synchronous repository"""

    def test_save_without_refresh_created_at_is_none(self, refresh_repo, db_test):
        """Test if created_at is None after save() without refresh()"""
        # Create instance without setting created_at/updated_at
        instance = RefreshTestModel(name="Test Item")

        # Before save, created_at should be None
        assert instance.created_at is None
        assert instance.updated_at is None

        # Save without refresh
        saved = refresh_repo.save(instance)

        # CRITICAL TEST: Are created_at/updated_at still None?
        print(f"\nAfter save (no refresh):")
        print(f"  created_at: {saved.created_at}")
        print(f"  updated_at: {saved.updated_at}")

        # If the issue document is correct, these should be None
        # But let's verify what actually happens
        is_created_at_none = saved.created_at is None
        is_updated_at_none = saved.updated_at is None

        print(f"\nVerification:")
        print(f"  created_at is None: {is_created_at_none}")
        print(f"  updated_at is None: {is_updated_at_none}")

        # Let's also check if database has the values
        db_test.commit()  # Ensure database is updated
        fetched = db_test.query(RefreshTestModel).filter_by(id=saved.id).first()

        print(f"\nFetched from database:")
        print(f"  created_at: {fetched.created_at}")
        print(f"  updated_at: {fetched.updated_at}")

        # Verify the results
        assert fetched.created_at is not None
        assert fetched.updated_at is not None

    def test_save_with_manual_refresh(self, refresh_repo, db_test):
        """Test if manual refresh() fixes the issue"""
        instance = RefreshTestModel(name="Test Item 2")
        saved = refresh_repo.save(instance)

        # Manually refresh
        db_test.refresh(saved)

        print(f"\nAfter save + manual refresh:")
        print(f"  created_at: {saved.created_at}")
        print(f"  updated_at: {saved.updated_at}")

        # After refresh, these should NOT be None
        assert saved.created_at is not None
        assert isinstance(saved.created_at, datetime)
        assert saved.updated_at is not None
        assert isinstance(saved.updated_at, datetime)


@pytest.mark.asyncio
class TestRefreshBehaviorAsync:
    """Test refresh behavior for asynchronous repository"""

    async def test_save_without_refresh_created_at_is_none(self, async_refresh_repo):
        """Test if created_at is None after save() without refresh() (async)"""
        repo = async_refresh_repo

        # Create instance without setting created_at/updated_at
        instance = RefreshTestModel(name="Test Item Async")

        # Before save
        assert instance.created_at is None
        assert instance.updated_at is None

        # Save without refresh
        saved = await repo.save(instance)

        print(f"\n[ASYNC] After save (no refresh):")
        print(f"  created_at: {saved.created_at}")
        print(f"  updated_at: {saved.updated_at}")

        is_created_at_none = saved.created_at is None
        is_updated_at_none = saved.updated_at is None

        print(f"\n[ASYNC] Verification:")
        print(f"  created_at is None: {is_created_at_none}")
        print(f"  updated_at is None: {is_updated_at_none}")

        # Verify the results
        assert saved.created_at is not None
        assert saved.updated_at is not None

    async def test_save_with_manual_refresh(self, async_refresh_repo, async_db_test):
        """Test if manual refresh() fixes the issue (async)"""
        repo = async_refresh_repo

        instance = RefreshTestModel(name="Test Item Async 2")
        saved = await repo.save(instance)

        # Manually refresh
        await async_db_test.refresh(saved)

        print(f"\n[ASYNC] After save + manual refresh:")
        print(f"  created_at: {saved.created_at}")
        print(f"  updated_at: {saved.updated_at}")

        # After refresh, these should NOT be None
        assert saved.created_at is not None
        assert isinstance(saved.created_at, datetime)
        assert saved.updated_at is not None
        assert isinstance(saved.updated_at, datetime)
