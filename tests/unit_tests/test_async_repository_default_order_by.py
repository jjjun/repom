"""
AsyncBaseRepository の default_order_by のテスト

order_by=None および空文字が渡された場合に default_order_by が
正しく適用されることをテストします（非同期版）。
"""
from tests._init import *
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
import pytest
from repom.base_model import BaseModel
from repom.repositories import AsyncBaseRepository


# テスト用モデル定義
class AsyncOrderTestModel(BaseModel):
    __tablename__ = 'async_order_test_items'
    
    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


# default_order_by を設定したリポジトリ
class AsyncOrderTestRepository(AsyncBaseRepository[AsyncOrderTestModel]):
    allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']
    default_order_by = 'id:desc'
    
    def __init__(self, session):
        super().__init__(AsyncOrderTestModel, session)


# default_order_by なしのリポジトリ
class SimpleAsyncOrderRepository(AsyncBaseRepository[AsyncOrderTestModel]):
    allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']
    
    def __init__(self, session):
        super().__init__(AsyncOrderTestModel, session)


class TestAsyncDefaultOrderBy:
    """default_order_by の動作をテスト（非同期版）"""
    
    @pytest.mark.asyncio
    async def test_find_without_order_by_uses_default(self, async_db_test):
        """order_by 未指定の場合、default_order_by が適用される"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find()
        
        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == item3.id
        assert results[1].id == item2.id
        assert results[2].id == item1.id
    
    @pytest.mark.asyncio
    async def test_find_with_none_uses_default(self, async_db_test):
        """order_by=None の場合、default_order_by が適用される"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find(order_by=None)
        
        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == item3.id
        assert results[1].id == item2.id
        assert results[2].id == item1.id
    
    @pytest.mark.asyncio
    async def test_find_with_empty_string_uses_default(self, async_db_test):
        """order_by="" の場合、default_order_by が適用される"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find(order_by="")
        
        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == item3.id
        assert results[1].id == item2.id
        assert results[2].id == item1.id
    
    @pytest.mark.asyncio
    async def test_find_with_explicit_order_overrides_default(self, async_db_test):
        """明示的な order_by が default_order_by を上書きする"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find(order_by='id:asc')
        
        # 明示的に id:asc を指定したので昇順
        assert len(results) == 3
        assert results[0].id == item1.id
        assert results[1].id == item2.id
        assert results[2].id == item3.id
    
    @pytest.mark.asyncio
    async def test_find_with_different_column_order(self, async_db_test):
        """別カラムでのソート指定が default_order_by を上書きする"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        await repo.save(AsyncOrderTestModel(name='First', priority=1))
        await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find(order_by='priority:asc')
        
        # priority 昇順でソート
        assert len(results) == 3
        assert results[0].priority == 1
        assert results[1].priority == 2
        assert results[2].priority == 3
    
    @pytest.mark.asyncio
    async def test_find_without_default_order_by_uses_fallback(self, async_db_test):
        """default_order_by なしの場合、id:asc がフォールバック"""
        repo = SimpleAsyncOrderRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find()
        
        # default_order_by がないので id:asc（フォールバック）
        assert len(results) == 3
        assert results[0].id == item1.id
        assert results[1].id == item2.id
        assert results[2].id == item3.id
    
    @pytest.mark.asyncio
    async def test_find_without_default_and_none_uses_fallback(self, async_db_test):
        """default_order_by なしで order_by=None の場合も id:asc がフォールバック"""
        repo = SimpleAsyncOrderRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find(order_by=None)
        
        # default_order_by がないので id:asc（フォールバック）
        assert len(results) == 3
        assert results[0].id == item1.id
        assert results[1].id == item2.id
        assert results[2].id == item3.id


class TestAsyncDefaultOrderByEdgeCases:
    """エッジケースのテスト（非同期版）"""
    
    @pytest.mark.asyncio
    async def test_default_order_by_with_sqlalchemy_expression(self, async_db_test):
        """default_order_by に SQLAlchemy 式を指定した場合"""
        from sqlalchemy import desc
        
        class ExpressionOrderRepository(AsyncBaseRepository[AsyncOrderTestModel]):
            default_order_by = desc(AsyncOrderTestModel.priority)
            
            def __init__(self, session):
                super().__init__(AsyncOrderTestModel, session)
        
        repo = ExpressionOrderRepository(session=async_db_test)
        
        await repo.save(AsyncOrderTestModel(name='First', priority=1))
        await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        results = await repo.find()
        
        # priority の降順
        assert results[0].priority == 3
        assert results[1].priority == 2
        assert results[2].priority == 1


class TestAsyncDefaultOrderByFastAPIPattern:
    """FastAPI の Query(None) パターンとの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_fastapi_query_none_pattern(self, async_db_test):
        """FastAPI の Query(None) パターンをシミュレート"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        # FastAPI エンドポイントでクエリパラメータなしの場合
        # order_by: str = Query(None) → order_by=None が渡される
        def simulated_fastapi_endpoint(order_by: str = None):
            return order_by
        
        order_by_param = simulated_fastapi_endpoint()  # None が返る
        results = await repo.find(order_by=order_by_param)
        
        # default_order_by が適用される
        assert results[0].id == item3.id
        assert results[1].id == item2.id
        assert results[2].id == item1.id
    
    @pytest.mark.asyncio
    async def test_fastapi_query_empty_string_pattern(self, async_db_test):
        """FastAPI で空文字が渡された場合のパターン"""
        repo = AsyncOrderTestRepository(session=async_db_test)
        
        # テストデータ作成
        item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
        item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
        item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
        
        # FastAPI で ?order_by= のように空文字が渡される場合
        results = await repo.find(order_by="")
        
        # default_order_by が適用される
        assert results[0].id == item3.id
        assert results[1].id == item2.id
        assert results[2].id == item1.id
