# Testing Guides

repom を使ったテストの書き方とベストプラクティスです。

## 📋 ガイド一覧

- **[testing_guide.md](testing_guide.md)** - テスト戦略とフィクスチャの使い方
- **[fixture_guide.md](fixture_guide.md)** - pytest フィクスチャの基本とベストプラクティス

## 🎯 このディレクトリの対象

- Transaction Rollback パターン
- テストフィクスチャの使い方
- テストモデルの使い分け (`tests/fixtures/models/` vs `isolated_mapper_registry`)
- pytest 設定
- テストのベストプラクティス

## 🚀 クイックスタート

### 推奨: tests/fixtures/models/ のモデルを使用

通常のテストでは、事前定義されたモデルを使用します：

```python
from tests.fixtures.models import User, Post, Parent, Child

def test_user_crud(db_test):
    user = User(name="Alice", email="alice@example.com")
    repo = BaseRepository(User, session=db_test)
    repo.save(user)
    
    fetched_user = repo.get_by_id(user.id)
    assert fetched_user.name == "Alice"
```

### 特殊ケース: isolated_mapper_registry

TYPE_CHECKING ブロックのテストや動的モデル定義が必要な場合のみ使用：

```python
def test_type_checking(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp'
        name: Mapped[str]
    
    BaseModel.metadata.create_all(bind=db_test.bind)
    # ...
```

詳細は [testing_guide.md](testing_guide.md) を参照してください。
