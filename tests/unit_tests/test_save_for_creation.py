"""
Test to verify if save() method can be used for entity creation (not just updates)
"""
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model import BaseModel
from repom.repositories import AsyncBaseRepository


class SaveCreationTestModel(BaseModel, use_created_at=True, use_updated_at=True):
    """Test model for save() creation pattern"""
    __tablename__ = 'save_creation_test_model'
    __table_args__ = {'extend_existing': True}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


@pytest_asyncio.fixture
async def save_repo(async_db_test):
    """SaveCreationTestModel 用のリポジトリフィクスチャ

    各テストでデータ作成パターンが異なるため、
    リポジトリのみを提供してデータは各テスト内で作成する。

    Returns:
        AsyncBaseRepository: SaveCreationTestModel のリポジトリ
    """
    return AsyncBaseRepository(SaveCreationTestModel, session=async_db_test)


@pytest.mark.asyncio
class TestSaveMethodForCreation:
    """Verify that save() method works for both creation and update"""

    async def test_save_method_for_new_entity_creation(self, save_repo):
        """Test: save() can be used for NEW entity creation with external session

        外部セッション使用時、save() は flush のみを実行します。
        created_at/updated_at の確認には明示的な refresh が必要です。
        """
        repo = save_repo

        # Create NEW entity (not yet in database)
        new_entity = SaveCreationTestModel(name="New Entity")

        print(f"\n[TEST] Before save():")
        print(f"  id: {new_entity.id}")
        print(f"  created_at: {new_entity.created_at}")
        print(f"  updated_at: {new_entity.updated_at}")

        # Use save() method (external session: flush only)
        saved_entity = await repo.save(new_entity)

        print(f"\n[TEST] After save() (before refresh):")
        print(f"  id: {saved_entity.id}")
        print(f"  created_at: {saved_entity.created_at}")
        print(f"  updated_at: {saved_entity.updated_at}")

        # 外部セッション使用時: id は設定されるが、created_at/updated_at はまだ None
        assert saved_entity.id is not None  # Auto-increment id was set by flush
        assert saved_entity.created_at is None  # Not refreshed yet
        assert saved_entity.updated_at is None  # Not refreshed yet

        print(f"\n✅ RESULT: save() works for NEW entity creation (flush mode)!")

    async def test_save_method_for_existing_entity_update(self, save_repo):
        """Test: save() can be used for EXISTING entity update"""
        repo = save_repo

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

    async def test_save_vs_manual_flush_comparison(self, save_repo, async_db_test):
        """Compare: save() vs manual add+flush pattern with external session

        外部セッション使用時、save() は flush のみを実行します。
        これは手動での add+flush パターンと同等の動作です。
        """
        repo = save_repo

        # Pattern 1: Using save() method (external session: flush only)
        entity1 = SaveCreationTestModel(name="Using save()")
        entity1 = await repo.save(entity1)

        print(f"\n[PATTERN 1] Using save() with external session:")
        print(f"  created_at: {entity1.created_at}")
        print(f"  Lines of code: 2 lines")

        # Pattern 2: Manual add + flush (同等の動作)
        entity2 = SaveCreationTestModel(name="Manual pattern")
        async_db_test.add(entity2)
        await async_db_test.flush()

        print(f"\n[PATTERN 2] Manual add+flush:")
        print(f"  created_at: {entity2.created_at}")
        print(f"  Lines of code: 2 lines")

        # 外部セッション使用時: 両方とも flush のみなので created_at は None
        assert entity1.created_at is None
        assert entity2.created_at is None

        # 明示的に refresh すれば値が取得できる
        await async_db_test.refresh(entity1)
        await async_db_test.refresh(entity2)

        assert entity1.created_at is not None
        assert entity2.created_at is not None

        print(f"\n✅ RESULT: save() with external session = flush only (same as manual pattern)")
        print(f"   - Both patterns require explicit refresh for AutoDateTime values")


@pytest.mark.asyncio
class TestSaveMethodReplacesMinePatterns:
    """Verify that save() can replace the patterns used in mine-py"""

    async def test_mine_py_video_asset_link_pattern(self, save_repo):
        """Simulate the pattern from mine-py video_asset_routes.py with external session

        外部セッション使用時、save() は flush のみを実行するため、
        created_at/updated_at を取得するには明示的な refresh が必要です。

        ただし、トランザクション管理が簡潔になり、commit は呼び出し側で制御できます。
        """
        repo = save_repo

        # mine-py pattern (元のパターン):
        # link = AniVideoAssetLinkModel(...)
        # session.add(link)
        # await session.flush()
        # await session.refresh(link)  # これを忘れるとバグ
        # await session.commit()

        # 改善案: save() を使う（外部セッション: flush のみ）
        link = SaveCreationTestModel(name="Video Asset Link")
        link = await repo.save(link)

        # 外部セッション使用時: created_at/updated_at はまだ None
        # （flush のみ実行、refresh は実行されない）
        assert link.created_at is None
        assert link.updated_at is None

        # id は設定されている（flush で採番）
        assert link.id is not None

        print(f"\n✅ save() simplifies transaction management!")
        print(f"   - External session: save() = flush only")
        print(f"   - Commit is controlled by caller (with block)")
        print(f"   - Explicit refresh needed for AutoDateTime values")
