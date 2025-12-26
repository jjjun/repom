"""
Test to verify if save() method can be used for entity creation (not just updates)
"""
import pytest
from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model import BaseModel
from repom.async_base_repository import AsyncBaseRepository


class SaveCreationTestModel(BaseModel, use_created_at=True, use_updated_at=True):
    """Test model for save() creation pattern"""
    __tablename__ = 'save_creation_test_model'
    __table_args__ = {'extend_existing': True}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


@pytest.mark.asyncio
class TestSaveMethodForCreation:
    """Verify that save() method works for both creation and update"""

    async def test_save_method_for_new_entity_creation(self, async_db_test):
        """Test: save() can be used for NEW entity creation"""
        repo = AsyncBaseRepository(SaveCreationTestModel, session=async_db_test)

        # Create NEW entity (not yet in database)
        new_entity = SaveCreationTestModel(name="New Entity")

        print(f"\n[TEST] Before save():")
        print(f"  id: {new_entity.id}")
        print(f"  created_at: {new_entity.created_at}")
        print(f"  updated_at: {new_entity.updated_at}")

        # Use save() method
        saved_entity = await repo.save(new_entity)

        print(f"\n[TEST] After save():")
        print(f"  id: {saved_entity.id}")
        print(f"  created_at: {saved_entity.created_at}")
        print(f"  updated_at: {saved_entity.updated_at}")

        # Verify: NEW entity was created successfully
        assert saved_entity.id is not None  # Auto-increment id was set
        assert saved_entity.created_at is not None  # AutoDateTime was set
        assert saved_entity.updated_at is not None  # AutoDateTime was set
        assert isinstance(saved_entity.created_at, datetime)
        assert isinstance(saved_entity.updated_at, datetime)

        print(f"\n✅ RESULT: save() works for NEW entity creation!")

    async def test_save_method_for_existing_entity_update(self, async_db_test):
        """Test: save() can be used for EXISTING entity update"""
        repo = AsyncBaseRepository(SaveCreationTestModel, session=async_db_test)

        # First: Create entity
        entity = SaveCreationTestModel(name="Original Name")
        saved_entity = await repo.save(entity)
        original_created_at = saved_entity.created_at
        original_id = saved_entity.id

        print(f"\n[TEST] Original entity:")
        print(f"  id: {saved_entity.id}")
        print(f"  name: {saved_entity.name}")
        print(f"  created_at: {saved_entity.created_at}")

        # Second: Update entity
        saved_entity.name = "Updated Name"
        updated_entity = await repo.save(saved_entity)

        print(f"\n[TEST] After update:")
        print(f"  id: {updated_entity.id}")
        print(f"  name: {updated_entity.name}")
        print(f"  created_at: {updated_entity.created_at}")
        print(f"  updated_at: {updated_entity.updated_at}")

        # Verify: Entity was updated (not created again)
        assert updated_entity.id == original_id  # Same id
        assert updated_entity.name == "Updated Name"  # Name was updated
        assert updated_entity.created_at == original_created_at  # created_at unchanged

        print(f"\n✅ RESULT: save() works for EXISTING entity update!")

    async def test_save_vs_manual_flush_comparison(self, async_db_test):
        """Compare: save() vs manual add+flush+refresh pattern"""
        repo = AsyncBaseRepository(SaveCreationTestModel, session=async_db_test)

        # Pattern 1: Using save() method
        entity1 = SaveCreationTestModel(name="Using save()")
        entity1 = await repo.save(entity1)

        print(f"\n[PATTERN 1] Using save():")
        print(f"  created_at: {entity1.created_at}")
        print(f"  Lines of code: 2 lines")

        # Pattern 2: Manual add + flush + refresh + commit
        entity2 = SaveCreationTestModel(name="Manual pattern")
        async_db_test.add(entity2)
        await async_db_test.flush()
        await async_db_test.refresh(entity2)
        await async_db_test.commit()

        print(f"\n[PATTERN 2] Manual add+flush+refresh+commit:")
        print(f"  created_at: {entity2.created_at}")
        print(f"  Lines of code: 4 lines")

        # Both should have created_at set
        assert entity1.created_at is not None
        assert entity2.created_at is not None

        print(f"\n✅ RESULT: save() is simpler and safer!")
        print(f"   - save(): 2 lines, no mistakes possible")
        print(f"   - manual: 4 lines, easy to forget refresh()")


@pytest.mark.asyncio
class TestSaveMethodReplacesMinePatterns:
    """Verify that save() can replace the patterns used in mine-py"""

    async def test_mine_py_video_asset_link_pattern(self, async_db_test):
        """Simulate the pattern from mine-py video_asset_routes.py"""
        repo = AsyncBaseRepository(SaveCreationTestModel, session=async_db_test)

        # mine-py pattern (問題があるパターン):
        # link = AniVideoAssetLinkModel(...)
        # session.add(link)
        # await session.flush()
        # await session.refresh(link)  # これを忘れるとバグ
        # await session.commit()

        # 改善案: save() を使う
        link = SaveCreationTestModel(name="Video Asset Link")
        link = await repo.save(link)

        # created_at, updated_at が正しく設定されている
        assert link.created_at is not None
        assert link.updated_at is not None

        print(f"\n✅ mine-py pattern can be replaced with save()!")
        print(f"   Before: 5 lines (add + flush + refresh + commit)")
        print(f"   After:  2 lines (just save())")
