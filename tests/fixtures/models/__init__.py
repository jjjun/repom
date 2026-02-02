"""テストモデルの統一インターフェース

このモジュールは、repom のテストで使用する共通モデルを提供します。
全テストで再利用可能なモデルを定義し、Transaction Rollback パターンと組み合わせて使用します。

使用例:
    from tests.fixtures.models import User, Post
    
    def test_user_repository(db_test):
        user = User(name="Alice", email="alice@example.com")
        db_test.add(user)
        db_test.commit()
"""

from tests.fixtures.models.basic import User, Post
from tests.fixtures.models.relationship import Parent, Child

__all__ = [
    'User',
    'Post',
    'Parent',
    'Child',
]
