"""
BaseRepository の default_order_by のテスト

order_by=None および空文字が渡された場合に default_order_by が
正しく適用されることをテストします。
"""
from tests._init import *
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
import pytest
from repom.models.base_model import BaseModel
from repom.repositories import BaseRepository


# テスト用モデル定義
class OrderTestModel(BaseModel):
    __tablename__ = 'order_test_items'

    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


# default_order_by を設定したリポジトリ
class OrderTestRepository(BaseRepository[OrderTestModel]):
    allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']
    default_order_by = 'id:desc'

    def __init__(self, session):
        super().__init__(OrderTestModel, session)


# default_order_by なしのリポジトリ
class SimpleOrderRepository(BaseRepository[OrderTestModel]):
    allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']

    def __init__(self, session):
        super().__init__(OrderTestModel, session)


class TestDefaultOrderBy:
    """default_order_by の動作をテスト"""

    @pytest.fixture(autouse=True)
    def setup_method(self, db_test):
        """各テスト前にテストデータを作成"""
        repo = OrderTestRepository(session=db_test)

        # テストデータ作成（id: 1, 2, 3 の順）
        item1 = repo.save(OrderTestModel(name='First', priority=1))
        item2 = repo.save(OrderTestModel(name='Second', priority=2))
        item3 = repo.save(OrderTestModel(name='Third', priority=3))

        self.item1_id = item1.id
        self.item2_id = item2.id
        self.item3_id = item3.id

    def test_find_without_order_by_uses_default(self, db_test):
        """order_by 未指定の場合、default_order_by が適用される"""
        repo = OrderTestRepository(session=db_test)

        results = repo.find()

        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == self.item3_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item1_id

    def test_find_with_none_uses_default(self, db_test):
        """order_by=None の場合、default_order_by が適用される"""
        repo = OrderTestRepository(session=db_test)

        results = repo.find(order_by=None)

        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == self.item3_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item1_id

    def test_find_with_empty_string_uses_default(self, db_test):
        """order_by="" の場合、default_order_by が適用される"""
        repo = OrderTestRepository(session=db_test)

        results = repo.find(order_by="")

        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == self.item3_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item1_id

    def test_find_with_explicit_order_overrides_default(self, db_test):
        """明示的な order_by が default_order_by を上書きする"""
        repo = OrderTestRepository(session=db_test)

        results = repo.find(order_by='id:asc')

        # 明示的に id:asc を指定したので昇順
        assert len(results) == 3
        assert results[0].id == self.item1_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item3_id

    def test_find_with_different_column_order(self, db_test):
        """別カラムでのソート指定が default_order_by を上書きする"""
        repo = OrderTestRepository(session=db_test)

        results = repo.find(order_by='priority:asc')

        # priority 昇順でソート
        assert len(results) == 3
        assert results[0].priority == 1
        assert results[1].priority == 2
        assert results[2].priority == 3

    def test_find_without_default_order_by_uses_fallback(self, db_test):
        """default_order_by なしの場合、id:asc がフォールバック"""
        repo = SimpleOrderRepository(session=db_test)

        results = repo.find()

        # default_order_by がないので id:asc（フォールバック）
        assert len(results) == 3
        assert results[0].id == self.item1_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item3_id

    def test_find_without_default_and_none_uses_fallback(self, db_test):
        """default_order_by なしで order_by=None の場合も id:asc がフォールバック"""
        repo = SimpleOrderRepository(session=db_test)

        results = repo.find(order_by=None)

        # default_order_by がないので id:asc（フォールバック）
        assert len(results) == 3
        assert results[0].id == self.item1_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item3_id


class TestDefaultOrderByWithOtherMethods:
    """default_order_by が他のメソッドでも機能することをテスト"""

    @pytest.fixture(autouse=True)
    def setup_method(self, db_test):
        """各テスト前にテストデータを作成"""
        repo = OrderTestRepository(session=db_test)

        # テストデータ作成
        item1 = repo.save(OrderTestModel(name='First', priority=1))
        item2 = repo.save(OrderTestModel(name='Second', priority=2))
        item3 = repo.save(OrderTestModel(name='Third', priority=3))

        self.item1_id = item1.id
        self.item2_id = item2.id
        self.item3_id = item3.id

    def test_find_uses_default_order(self, db_test):
        """find() で default_order_by が適用される"""
        repo = OrderTestRepository(session=db_test)

        results = repo.find()

        # default_order_by = 'id:desc' なので降順
        assert len(results) == 3
        assert results[0].id == self.item3_id
        assert results[1].id == self.item2_id
        assert results[2].id == self.item1_id


class TestDefaultOrderByEdgeCases:
    """エッジケースのテスト"""

    def test_default_order_by_with_invalid_column(self, db_test):
        """default_order_by に無効なカラムを指定した場合"""
        class InvalidOrderRepository(BaseRepository[OrderTestModel]):
            default_order_by = 'invalid_column:desc'

            def __init__(self, session):
                super().__init__(OrderTestModel, session)

        repo = InvalidOrderRepository(session=db_test)
        repo.save(OrderTestModel(name='Test', priority=1))

        # 無効なカラムなのでエラーが発生すべき
        with pytest.raises(ValueError, match="not allowed for sorting"):
            repo.find()

    def test_default_order_by_with_sqlalchemy_expression(self, db_test):
        """default_order_by に SQLAlchemy 式を指定した場合"""
        from sqlalchemy import desc

        class ExpressionOrderRepository(BaseRepository[OrderTestModel]):
            default_order_by = desc(OrderTestModel.priority)

            def __init__(self, session):
                super().__init__(OrderTestModel, session)

        repo = ExpressionOrderRepository(session=db_test)

        item1 = repo.save(OrderTestModel(name='First', priority=1))
        item2 = repo.save(OrderTestModel(name='Second', priority=2))
        item3 = repo.save(OrderTestModel(name='Third', priority=3))

        results = repo.find()

        # priority の降順
        assert results[0].priority == 3
        assert results[1].priority == 2
        assert results[2].priority == 1
