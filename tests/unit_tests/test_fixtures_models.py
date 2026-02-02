"""tests/fixtures/models のモデルが正しく使えるかテスト"""
import pytest
from tests.fixtures.models import User, Post, Parent, Child
from repom import BaseRepository


def test_user_model_basic_crud(db_test):
    """User モデルの基本的な CRUD 操作"""
    repo = BaseRepository(User, session=db_test)
    
    # Create
    user = User(name="Alice", email="alice@example.com")
    repo.add(user)
    repo.commit()
    
    assert user.id is not None
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
    
    # Read
    found = repo.get_by_id(user.id)
    assert found is not None
    assert found.name == "Alice"
    
    # Update
    found.name = "Alice Updated"
    repo.commit()
    assert repo.get_by_id(user.id).name == "Alice Updated"
    
    # Delete
    repo.delete(found)
    repo.commit()
    assert repo.get_by_id(user.id) is None


def test_post_model_with_foreign_key(db_test):
    """Post モデルと外部キーのテスト"""
    user_repo = BaseRepository(User, session=db_test)
    post_repo = BaseRepository(Post, session=db_test)
    
    # User を作成
    user = User(name="Bob", email="bob@example.com")
    user_repo.add(user)
    user_repo.commit()
    
    # Post を作成（外部キー）
    post = Post(title="First Post", content="Hello World", user_id=user.id)
    post_repo.add(post)
    post_repo.commit()
    
    assert post.id is not None
    assert post.user_id == user.id


def test_user_post_relationship(db_test):
    """User と Post のリレーションシップテスト"""
    user_repo = BaseRepository(User, session=db_test)
    post_repo = BaseRepository(Post, session=db_test)
    
    # User を作成
    user = User(name="Charlie", email="charlie@example.com")
    user_repo.add(user)
    user_repo.commit()
    
    # 複数の Post を作成
    post1 = Post(title="Post 1", content="Content 1", user_id=user.id)
    post2 = Post(title="Post 2", content="Content 2", user_id=user.id)
    post_repo.add(post1)
    post_repo.add(post2)
    post_repo.commit()
    
    # リレーションシップを検証
    db_test.refresh(user)  # リレーションシップをロード
    assert len(user.posts) == 2
    assert user.posts[0].title in ["Post 1", "Post 2"]
    assert post1.user.name == "Charlie"


def test_parent_child_relationship(db_test):
    """Parent と Child のリレーションシップテスト"""
    parent_repo = BaseRepository(Parent, session=db_test)
    child_repo = BaseRepository(Child, session=db_test)
    
    # Parent を作成
    parent = Parent(name="Parent A")
    parent_repo.add(parent)
    parent_repo.commit()
    
    # 複数の Child を作成
    child1 = Child(name="Child 1", parent_id=parent.id)
    child2 = Child(name="Child 2", parent_id=parent.id)
    child_repo.add(child1)
    child_repo.add(child2)
    child_repo.commit()
    
    # リレーションシップを検証
    db_test.refresh(parent)
    assert len(parent.children) == 2
    assert child1.parent.name == "Parent A"
    assert child2.parent.name == "Parent A"


def test_cascade_delete(db_test):
    """cascade='all, delete-orphan' のテスト"""
    parent_repo = BaseRepository(Parent, session=db_test)
    child_repo = BaseRepository(Child, session=db_test)
    
    # Parent と Child を作成
    parent = Parent(name="Parent B")
    child = Child(name="Child B", parent=parent)
    parent_repo.add(parent)
    parent_repo.commit()
    
    parent_id = parent.id
    child_id = child.id
    
    # Parent を削除
    parent_repo.delete(parent)
    parent_repo.commit()
    
    # Child も削除されているか確認
    assert parent_repo.get_by_id(parent_id) is None
    assert child_repo.get_by_id(child_id) is None
