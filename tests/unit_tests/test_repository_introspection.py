"""Tests for repom.repositories introspection helpers.

Pattern A (subclass without ``__init__``) と Pattern B (subclass が独自
``__init__`` を持つ) の双方で create_repository_instance が
適切な呼び出し規約を選ぶことを検証する。
"""

from __future__ import annotations

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseRepository
from repom.models import BaseModel
from repom.repositories import (
    AsyncBaseRepository,
    create_repository_instance,
    get_model_from_repository_class,
)


class IntrospectionModel(BaseModel):
    """Test model for introspection helpers."""

    __tablename__ = "test_introspection_model"

    name: Mapped[str] = mapped_column(String(100))


class PatternARepository(BaseRepository[IntrospectionModel]):
    """Pattern A: ``__init__`` 未定義、 model は Generic 経由で推論。"""


class PatternBRepository(BaseRepository[IntrospectionModel]):
    """Pattern B: 独自 ``__init__`` を持ち session のみを受け取る。"""

    def __init__(self, session=None):
        super().__init__(IntrospectionModel, session)
        self.custom_marker = "pattern-b"


class AsyncPatternARepository(AsyncBaseRepository[IntrospectionModel]):
    """Async Pattern A."""


class AsyncPatternBRepository(AsyncBaseRepository[IntrospectionModel]):
    """Async Pattern B (独自 ``__init__``)。"""

    def __init__(self, session=None):
        super().__init__(IntrospectionModel, session)
        self.custom_marker = "async-pattern-b"


class TestGetModelFromRepositoryClass:
    """get_model_from_repository_class の動作確認"""

    def test_pattern_a_sync(self):
        assert (
            get_model_from_repository_class(PatternARepository)
            is IntrospectionModel
        )

    def test_pattern_b_sync(self):
        # Pattern B でも Generic パラメータは保持されているので取れる
        assert (
            get_model_from_repository_class(PatternBRepository)
            is IntrospectionModel
        )

    def test_pattern_a_async(self):
        assert (
            get_model_from_repository_class(AsyncPatternARepository)
            is IntrospectionModel
        )

    def test_raises_for_class_without_generic(self):
        class NotARepository:
            pass

        with pytest.raises(TypeError, match="Could not extract model"):
            get_model_from_repository_class(NotARepository)


class TestCreateRepositoryInstanceSync:
    """同期 repository に対する create_repository_instance"""

    def test_pattern_a_uses_model_and_session(self, db_test):
        repo = create_repository_instance(PatternARepository, db_test)

        assert isinstance(repo, PatternARepository)
        assert repo.model is IntrospectionModel
        # find() がエラーなく動作する
        assert isinstance(repo.find(), list)

    def test_pattern_b_uses_session_only(self, db_test):
        repo = create_repository_instance(PatternBRepository, db_test)

        assert isinstance(repo, PatternBRepository)
        assert repo.model is IntrospectionModel
        # 独自 __init__ で設定したフィールドが反映されていることを確認
        assert repo.custom_marker == "pattern-b"


class TestCreateRepositoryInstanceAsync:
    """非同期 repository に対する create_repository_instance"""

    def test_async_pattern_a_uses_model_and_session(self):
        # AsyncSession を本物で組み立てる必要は無く、 引数経路を確認できれば良い
        sentinel = object()
        repo = create_repository_instance(AsyncPatternARepository, sentinel)

        assert isinstance(repo, AsyncPatternARepository)
        assert repo.model is IntrospectionModel
        # framework __init__ 経由で session が _session_override に入る
        assert repo._session_override is sentinel

    def test_async_pattern_b_uses_session_only(self):
        sentinel = object()
        repo = create_repository_instance(AsyncPatternBRepository, sentinel)

        assert isinstance(repo, AsyncPatternBRepository)
        assert repo.model is IntrospectionModel
        assert repo.custom_marker == "async-pattern-b"
        assert repo._session_override is sentinel
