"""
Test to verify if refresh() is needed after flush() for AutoDateTime fields.

This test verifies the issue described in:
mine-py/docs/issues/active/repo-flush-refresh-pattern.md
"""
import pytest
from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.models.base_model import BaseModel
from repom import BaseRepository, AsyncBaseRepository


class FlushTestModel(BaseModel, use_created_at=True, use_updated_at=True):
    """Test model with AutoDateTime fields"""
    __tablename__ = 'flush_test_model'
    __table_args__ = {'extend_existing': True}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class TestFlushRefreshPatternSync:
    """Test flush + refresh pattern for synchronous repository"""

    def test_flush_without_refresh_created_at_is_none(self, db_test):
        """Test if created_at is None after flush() without refresh() - SYNC"""
        instance = FlushTestModel(name="Test Item")

        # Before flush
        assert instance.created_at is None
        assert instance.updated_at is None

        # Pattern from issue: add + flush (without refresh)
        db_test.add(instance)
        db_test.flush()

        print(f"\n[SYNC] After flush (no refresh):")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        is_created_at_none = instance.created_at is None
        is_updated_at_none = instance.updated_at is None

        print(f"\n[SYNC] Verification:")
        print(f"  created_at is None: {is_created_at_none}")
        print(f"  updated_at is None: {is_updated_at_none}")

        # If issue is correct, these should be None
        # But let's see actual behavior

    def test_flush_with_refresh_has_values(self, db_test):
        """Test if created_at is set after flush() + refresh() - SYNC"""
        instance = FlushTestModel(name="Test Item 2")

        # Pattern with refresh
        db_test.add(instance)
        db_test.flush()
        db_test.refresh(instance)

        print(f"\n[SYNC] After flush + refresh:")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        # After refresh, these should NOT be None
        assert instance.created_at is not None
        assert isinstance(instance.created_at, datetime)
        assert instance.updated_at is not None
        assert isinstance(instance.updated_at, datetime)

    def test_commit_without_refresh_auto_loads(self, db_test):
        """Test if commit() triggers auto-load on attribute access - SYNC"""
        instance = FlushTestModel(name="Test Item 3")

        db_test.add(instance)
        db_test.flush()
        db_test.commit()

        # After commit, try to access created_at
        # Sync session should auto-load it due to expire_on_commit
        print(f"\n[SYNC] After flush + commit (accessing attribute):")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        # Should auto-load due to expire_on_commit
        assert instance.created_at is not None
        assert instance.updated_at is not None


@pytest.mark.asyncio
class TestFlushRefreshPatternAsync:
    """Test flush + refresh pattern for asynchronous repository"""

    async def test_flush_without_refresh_created_at_is_none(self, async_db_test):
        """Test if created_at is None after flush() without refresh() - ASYNC"""
        instance = FlushTestModel(name="Test Item Async")

        # Before flush
        assert instance.created_at is None
        assert instance.updated_at is None

        # Pattern from issue: add + flush (without refresh)
        async_db_test.add(instance)
        await async_db_test.flush()

        print(f"\n[ASYNC] After flush (no refresh):")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        is_created_at_none = instance.created_at is None
        is_updated_at_none = instance.updated_at is None

        print(f"\n[ASYNC] Verification:")
        print(f"  created_at is None: {is_created_at_none}")
        print(f"  updated_at is None: {is_updated_at_none}")

        # According to issue, these should be None
        # Let's verify

    async def test_flush_with_refresh_has_values(self, async_db_test):
        """Test if created_at is set after flush() + refresh() - ASYNC"""
        instance = FlushTestModel(name="Test Item Async 2")

        # Pattern with refresh
        async_db_test.add(instance)
        await async_db_test.flush()
        await async_db_test.refresh(instance)

        print(f"\n[ASYNC] After flush + refresh:")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        # After refresh, these should NOT be None
        assert instance.created_at is not None
        assert isinstance(instance.created_at, datetime)
        assert instance.updated_at is not None
        assert isinstance(instance.updated_at, datetime)

    async def test_commit_without_refresh_still_none(self, async_db_test):
        """Test if commit() does NOT auto-load in async - ASYNC"""
        instance = FlushTestModel(name="Test Item Async 3")

        async_db_test.add(instance)
        await async_db_test.flush()
        await async_db_test.commit()

        # After commit, try to access created_at
        # Async session does NOT auto-load
        print(f"\n[ASYNC] After flush + commit (accessing attribute):")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        # Should still be None in async


@pytest.mark.asyncio
class TestRepositorySaveVsFlush:
    """Compare save() method vs flush() pattern"""

    async def test_save_method_automatically_refreshes(self, async_db_test):
        """Test that save() method handles refresh automatically with external session

        Note: 外部セッション使用時は flush のみ実行され、refresh は実行されません。
        そのため、created_at/updated_at は flush 時点では None です。
        明示的な refresh が必要な場合は、手動で実行してください。
        """
        repo = AsyncBaseRepository(FlushTestModel, session=async_db_test)

        instance = FlushTestModel(name="Via save() method")
        saved = await repo.save(instance)

        print(f"\n[COMPARE] Using repo.save() with external session:")
        print(f"  created_at (before refresh): {saved.created_at}")
        print(f"  updated_at (before refresh): {saved.updated_at}")

        # 外部セッション使用時: save() は flush のみ実行、refresh は実行されない
        # created_at/updated_at はまだ None
        assert saved.created_at is None
        assert saved.updated_at is None

        # 明示的に refresh すれば値が取得できる
        await async_db_test.refresh(saved)
        assert saved.created_at is not None
        assert saved.updated_at is not None

    async def test_manual_flush_needs_refresh(self, async_db_test):
        """Test that manual flush() needs explicit refresh()"""
        instance = FlushTestModel(name="Via manual flush")

        async_db_test.add(instance)
        await async_db_test.flush()
        # Deliberately NOT calling refresh()

        print(f"\n[COMPARE] Using manual flush (no refresh):")
        print(f"  created_at: {instance.created_at}")
        print(f"  updated_at: {instance.updated_at}")

        # Without refresh, these might be None
        # This is the problem described in the issue
