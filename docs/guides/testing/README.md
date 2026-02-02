# Testing Guides

repom を使ったテストの書き方とベストプラクティスです。

## 📋 ガイド一覧

- **[testing_guide.md](testing_guide.md)** - テスト戦略とフィクスチャの使い方
- **[fixture_guide.md](fixture_guide.md)** - pytest フィクスチャの基本とベストプラクティス

## 🎯 このディレクトリの対象

- Transaction Rollback パターン
- テストフィクスチャの使い方
- テストモデルの使い分け (`tests/fixtures/models/` vs 動的定義 + cleanup)
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

### 特殊ケース: マッパークリーンアップが必要なテスト

TYPE_CHECKING ブロックのテストや動的モデル定義が必要な場合:

```python
def test_type_checking(db_test):
    """
    TYPE_CHECKING ブロックの動作検証
    
    注意: テスト内でモデルを動的に定義するため、
           マッパーのクリーンアップが必要
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
    
    try:
        class TempModel(BaseModel):
            __tablename__ = 'temp'
            name: Mapped[str]
        
        BaseModel.metadata.create_all(bind=db_test.bind)
        # ...
    finally:
        clear_mappers()
        configure_mappers()
```

詳細は [testing_guide.md](testing_guide.md) を参照してください。
