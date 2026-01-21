"""
Test different repository initialization patterns
"""
import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.models.base_model import BaseModel
from repom import BaseRepository, AsyncBaseRepository


class InitTestModel(BaseModel):
    """Test model for repository initialization"""
    __tablename__ = 'init_test_model'
    __table_args__ = {'extend_existing': True}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class TestRepositoryInitPatterns:
    """Test different ways to initialize repository"""

    def test_pattern1_with_custom_init(self, db_test):
        """Pattern 1: Custom __init__ (過去の書き方)"""

        class CustomInitRepository(BaseRepository[InitTestModel]):
            def __init__(self, session):
                super().__init__(InitTestModel, session)

        # モデルを渡さずにインスタンス化
        repo = CustomInitRepository(session=db_test)

        print(f"\n[Pattern 1] Custom __init__:")
        print(f"  repo.model: {repo.model}")
        print(f"  repo.session: {repo.session}")

        assert repo.model == InitTestModel
        assert repo.session == db_test

        # 動作確認
        item = InitTestModel(name="Test 1")
        saved = repo.save(item)
        assert saved.name == "Test 1"

        print(f"  ✅ Works! Can create without passing model")

    def test_pattern2_without_custom_init(self, db_test):
        """Pattern 2: No custom __init__ (新しい書き方?)"""

        class NoInitRepository(BaseRepository[InitTestModel]):
            pass  # __init__ を省略

        # この場合、モデルを渡す必要がある
        try:
            # ❌ これはエラーになる
            repo = NoInitRepository(session=db_test)
            print(f"\n[Pattern 2] No __init__ (session only):")
            print(f"  ❌ This should fail but didn't?")
            assert False, "Expected TypeError"
        except TypeError as e:
            print(f"\n[Pattern 2] No __init__ (session only):")
            print(f"  ❌ Error (expected): {e}")
            assert "missing 1 required positional argument: 'model'" in str(e)

    def test_pattern3_without_custom_init_but_pass_model(self, db_test):
        """Pattern 3: No custom __init__, but pass model explicitly"""

        class NoInitRepository(BaseRepository[InitTestModel]):
            pass  # __init__ を省略

        # ✅ モデルを明示的に渡せば動作する
        repo = NoInitRepository(InitTestModel, session=db_test)

        print(f"\n[Pattern 3] No __init__ (pass model explicitly):")
        print(f"  repo.model: {repo.model}")
        print(f"  repo.session: {repo.session}")

        assert repo.model == InitTestModel
        assert repo.session == db_test

        # 動作確認
        item = InitTestModel(name="Test 3")
        saved = repo.save(item)
        assert saved.name == "Test 3"

        print(f"  ✅ Works! But need to pass model")

    def test_pattern4_direct_base_repository(self, db_test):
        """Pattern 4: Use BaseRepository directly (no subclass)"""

        # ✅ 直接 BaseRepository を使う
        repo = BaseRepository(InitTestModel, session=db_test)

        print(f"\n[Pattern 4] Direct BaseRepository:")
        print(f"  repo.model: {repo.model}")
        print(f"  repo.session: {repo.session}")

        assert repo.model == InitTestModel
        assert repo.session == db_test

        # 動作確認
        item = InitTestModel(name="Test 4")
        saved = repo.save(item)
        assert saved.name == "Test 4"

        print(f"  ✅ Works! Simplest way")


@pytest.mark.asyncio
class TestAsyncRepositoryInitPatterns:
    """Test async repository initialization patterns"""

    async def test_async_pattern1_with_custom_init(self, async_db_test):
        """Pattern 1: Custom __init__ (過去の書き方) - ASYNC"""

        class CustomInitAsyncRepository(AsyncBaseRepository[InitTestModel]):
            def __init__(self, session):
                super().__init__(InitTestModel, session)

        # モデルを渡さずにインスタンス化
        repo = CustomInitAsyncRepository(session=async_db_test)

        print(f"\n[Async Pattern 1] Custom __init__:")
        print(f"  repo.model: {repo.model}")
        print(f"  repo.session: {repo.session}")

        assert repo.model == InitTestModel
        assert repo.session == async_db_test

        # 動作確認
        item = InitTestModel(name="Async Test 1")
        saved = await repo.save(item)
        assert saved.name == "Async Test 1"

        print(f"  ✅ Works! Can create without passing model")

    async def test_async_pattern2_without_custom_init(self, async_db_test):
        """Pattern 2: No custom __init__ (新しい書き方?) - ASYNC"""

        class NoInitAsyncRepository(AsyncBaseRepository[InitTestModel]):
            pass  # __init__ を省略

        # この場合、モデルを渡す必要がある
        try:
            # ❌ これはエラーになる
            repo = NoInitAsyncRepository(session=async_db_test)
            print(f"\n[Async Pattern 2] No __init__ (session only):")
            print(f"  ❌ This should fail but didn't?")
            assert False, "Expected TypeError"
        except TypeError as e:
            print(f"\n[Async Pattern 2] No __init__ (session only):")
            print(f"  ❌ Error (expected): {e}")
            assert "missing 1 required positional argument: 'model'" in str(e)

    async def test_async_pattern3_without_custom_init_but_pass_model(self, async_db_test):
        """Pattern 3: No custom __init__, but pass model explicitly - ASYNC"""

        class NoInitAsyncRepository(AsyncBaseRepository[InitTestModel]):
            pass  # __init__ を省略

        # ✅ モデルを明示的に渡せば動作する
        repo = NoInitAsyncRepository(InitTestModel, session=async_db_test)

        print(f"\n[Async Pattern 3] No __init__ (pass model explicitly):")
        print(f"  repo.model: {repo.model}")
        print(f"  repo.session: {repo.session}")

        assert repo.model == InitTestModel
        assert repo.session == async_db_test

        # 動作確認
        item = InitTestModel(name="Async Test 3")
        saved = await repo.save(item)
        assert saved.name == "Async Test 3"

        print(f"  ✅ Works! But need to pass model")


class TestBestPracticeRecommendation:
    """推奨パターンの比較"""

    def test_compare_all_patterns(self, db_test):
        """すべてのパターンを比較"""

        print(f"\n{'='*60}")
        print(f"パターン比較")
        print(f"{'='*60}")

        # Pattern 1: Custom __init__ (過去の書き方)
        class Pattern1Repo(BaseRepository[InitTestModel]):
            def __init__(self, session):
                super().__init__(InitTestModel, session)

        repo1 = Pattern1Repo(session=db_test)
        print(f"\nPattern 1 (Custom __init__):")
        print(f"  インスタンス化: Pattern1Repo(session=db_test)")
        print(f"  コード量: 3行 (__init__ 定義が必要)")
        print(f"  メリット: モデル名を省略できる")
        print(f"  デメリット: __init__ の定義が冗長")

        # Pattern 2: No __init__ + pass model
        class Pattern2Repo(BaseRepository[InitTestModel]):
            pass

        repo2 = Pattern2Repo(InitTestModel, session=db_test)
        print(f"\nPattern 2 (No __init__ + pass model):")
        print(f"  インスタンス化: Pattern2Repo(InitTestModel, session=db_test)")
        print(f"  コード量: 1行 (pass のみ)")
        print(f"  メリット: __init__ 定義不要")
        print(f"  デメリット: モデル名を毎回渡す必要がある")

        # Pattern 3: Direct BaseRepository
        repo3 = BaseRepository(InitTestModel, session=db_test)
        print(f"\nPattern 3 (Direct BaseRepository):")
        print(f"  インスタンス化: BaseRepository(InitTestModel, session=db_test)")
        print(f"  コード量: 0行 (クラス定義不要)")
        print(f"  メリット: 最もシンプル")
        print(f"  デメリット: カスタムメソッドを追加できない")

        print(f"\n{'='*60}")
        print(f"✅ 推奨パターン:")
        print(f"  - カスタムメソッドが必要 → Pattern 1")
        print(f"  - カスタムメソッド不要 → Pattern 3")
        print(f"{'='*60}")

        # すべてのパターンが動作することを確認
        for i, repo in enumerate([repo1, repo2, repo3], 1):
            item = InitTestModel(name=f"Pattern {i}")
            saved = repo.save(item)
            assert saved.name == f"Pattern {i}"
