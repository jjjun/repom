# テストフィクスチャガイド

pytest フィクスチャの使い方とベストプラクティスをまとめたガイドです。

## 📋 目次

- [フィクスチャとは](#フィクスチャとは)
- [基本的な使い方](#基本的な使い方)
- [非同期フィクスチャ](#非同期フィクスチャ)
- [フィクスチャのスコープ](#フィクスチャのスコープ)
- [ベストプラクティス](#ベストプラクティス)
- [よくある問題と解決策](#よくある問題と解決策)

---

## フィクスチャとは

**フィクスチャ (Fixture)** は、テストで共通的に使用するデータやリソースのセットアップを行う pytest の機能です。

### フィクスチャを使うべき理由

✅ **DRY原則**: テストデータ作成ロジックを1箇所に集約  
✅ **可読性**: テストは「何をテストするか」だけに集中できる  
✅ **保守性**: データ構造変更はフィクスチャだけ修正すればOK  
✅ **一貫性**: 同じデータセットを複数のテストで再利用できる  

### ❌ アンチパターン: インラインデータ作成

```python
# 悪い例：各テストでデータを作成
class TestUser:
    def test_find_users(self, db_test):
        repo = UserRepository(session=db_test)
        user1 = repo.save(User(name='Alice'))  # データ作成
        user2 = repo.save(User(name='Bob'))
        user3 = repo.save(User(name='Charlie'))
        
        results = repo.find()
        assert len(results) == 3
    
    def test_get_user_by_id(self, db_test):
        repo = UserRepository(session=db_test)
        user1 = repo.save(User(name='Alice'))  # 同じデータを再作成
        user2 = repo.save(User(name='Bob'))
        user3 = repo.save(User(name='Charlie'))
        
        user = repo.get_by_id(user1.id)
        assert user.name == 'Alice'
```

**問題点:**
- コードの重複が多い（DRY原則違反）
- データ構造変更時に全テストを修正する必要がある
- テストの意図が埋もれて読みにくい

---

## 基本的な使い方

### 1. 同期フィクスチャの定義

```python
import pytest
from repom import BaseRepository

@pytest.fixture
def setup_users(db_test):
    """ユーザーテスト用のセットアップフィクスチャ"""
    repo = UserRepository(session=db_test)
    user1 = repo.save(User(name='Alice', age=25))
    user2 = repo.save(User(name='Bob', age=30))
    user3 = repo.save(User(name='Charlie', age=35))
    
    return {
        'repo': repo,
        'user1': user1,
        'user2': user2,
        'user3': user3,
    }
```

### 2. テストでフィクスチャを使用

```python
class TestUserRepository:
    def test_find_all_users(self, setup_users):
        """フィクスチャを受け取って使用"""
        results = setup_users['repo'].find()
        assert len(results) == 3
    
    def test_get_user_by_id(self, setup_users):
        """同じフィクスチャを別のテストでも使用"""
        user = setup_users['repo'].get_by_id(setup_users['user1'].id)
        assert user.name == 'Alice'
    
    def test_filter_by_age(self, setup_users):
        """フィクスチャのデータを利用した検索テスト"""
        results = setup_users['repo'].find(filter_params={'age__gte': 30})
        assert len(results) == 2
```

### 3. メリット

✅ **データ作成が1箇所**: `setup_users` フィクスチャのみ  
✅ **テストが簡潔**: 各テストはロジックだけに集中  
✅ **保守性向上**: User の属性変更はフィクスチャだけ修正  

---

## 非同期フィクスチャ

### 基本パターン

```python
import pytest
from repom import AsyncBaseRepository

@pytest.fixture
async def setup_users(async_db_test):
    """非同期フィクスチャ（autouse=False）"""
    repo = AsyncUserRepository(session=async_db_test)
    user1 = await repo.save(AsyncUser(name='Alice', age=25))
    user2 = await repo.save(AsyncUser(name='Bob', age=30))
    user3 = await repo.save(AsyncUser(name='Charlie', age=35))
    
    return {
        'repo': repo,
        'user1': user1,
        'user2': user2,
        'user3': user3,
    }
```

### 非同期テストでの使用

```python
class TestAsyncUserRepository:
    @pytest.mark.asyncio
    async def test_find_all_users(self, setup_users):
        """非同期フィクスチャを受け取る"""
        data = await setup_users  # await で結果を取得
        results = await data['repo'].find()
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, setup_users):
        data = await setup_users
        user = await data['repo'].get_by_id(data['user1'].id)
        assert user.name == 'Alice'
```

### ⚠️ 重要: autouse=True は使えない

pytest-asyncio は **autouse=True の非同期フィクスチャをサポートしていません**。

```python
# ❌ これはエラーになる
@pytest.fixture(autouse=True)  # autouse=True は非同期で使えない
async def setup_method(async_db_test):
    repo = AsyncUserRepository(session=async_db_test)
    # ...
    return repo

# ✅ autouse=False（デフォルト）で明示的に指定
@pytest.fixture  # autouse=False がデフォルト
async def setup_method(async_db_test):
    repo = AsyncUserRepository(session=async_db_test)
    # ...
    return repo
```

**理由:**
- pytest は autouse フィクスチャを自動実行しますが、非同期関数の await を自動で行えない
- pytest 9 ではエラーになる予定（現在は警告）

**解決策:**
- autouse を使わず、各テストで明示的にフィクスチャを受け取る
- 同期フィクスチャで autouse=True を使いたい場合は、データ作成を同期的に行う

---

## フィクスチャのスコープ

フィクスチャのスコープを指定すると、フィクスチャの実行タイミングを制御できます。

### scope='function' (デフォルト)

```python
@pytest.fixture(scope='function')
def setup_users(db_test):
    """各テストごとに新しいデータを作成"""
    # テストが実行される度に呼ばれる
    return create_test_users(db_test)
```

**特徴:**
- 各テスト関数ごとに1回実行
- テスト間でデータが完全に分離される
- **推奨**: ほとんどのケースでこれを使う

### scope='class'

```python
@pytest.fixture(scope='class')
def setup_users(db_test):
    """クラス内の全テストで同じデータを共有"""
    # クラスごとに1回だけ呼ばれる
    return create_test_users(db_test)
```

**特徴:**
- テストクラス単位で1回実行
- クラス内の全テストでデータを共有
- **注意**: テストがデータを変更すると他のテストに影響する

### scope='module'

```python
@pytest.fixture(scope='module')
def setup_users(db_test):
    """モジュール内の全テストで同じデータを共有"""
    # モジュールごとに1回だけ呼ばれる
    return create_test_users(db_test)
```

**特徴:**
- テストファイル単位で1回実行
- 高速だが、テスト間の独立性が損なわれる
- **使用は慎重に**: 読み取り専用データに限る

### scope='session'

```python
@pytest.fixture(scope='session')
def db_engine():
    """テストセッション全体で1回だけ作成"""
    # 全テスト実行時に1回だけ呼ばれる
    return create_engine()
```

**特徴:**
- 全テスト実行時に1回だけ実行
- データベースエンジンなど、不変リソースに使う
- repom の `db_engine` フィクスチャがこれを使用

---

## ベストプラクティス

### 1. フィクスチャ名は明確に

```python
# ✅ 良い例
@pytest.fixture
def setup_users_with_posts(db_test):
    """ユーザーと投稿データを作成"""
    # ...

@pytest.fixture
def setup_admin_user(db_test):
    """管理者ユーザーを作成"""
    # ...

# ❌ 悪い例
@pytest.fixture
def data(db_test):  # 何のデータか不明
    # ...
```

### 2. 辞書で複数の値を返す

```python
# ✅ 良い例：キーで明確にアクセス
@pytest.fixture
def setup_users(db_test):
    return {
        'repo': repo,
        'admin': admin_user,
        'users': [user1, user2, user3],
    }

def test_find_users(setup_users):
    results = setup_users['repo'].find()
    assert len(results) == 4  # admin + 3 users

# ❌ 悪い例：タプルだとインデックスが不明瞭
@pytest.fixture
def setup_users(db_test):
    return repo, admin_user, [user1, user2, user3]

def test_find_users(setup_users):
    results = setup_users[0].find()  # 0 が何か分からない
```

### 3. フィクスチャは共通資産として扱う

```python
# tests/conftest.py に共通フィクスチャを定義
@pytest.fixture
def db_engine():
    """全テストで共有するDBエンジン"""
    engine = create_engine('sqlite:///:memory:')
    BaseModel.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_test(db_engine):
    """各テストごとにトランザクションを提供"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    transaction.rollback()
    connection.close()
```

### 4. docstring でフィクスチャの目的を明記

```python
@pytest.fixture
async def setup_method(async_db_test):
    """非同期テスト用のセットアップフィクスチャ
    
    テストデータ:
    - item1: name='First', priority=1
    - item2: name='Second', priority=2
    - item3: name='Third', priority=3
    
    Returns:
        dict: repo, item1, item2, item3 を含む辞書
    """
    repo = AsyncOrderTestRepository(session=async_db_test)
    item1 = await repo.save(AsyncOrderTestModel(name='First', priority=1))
    item2 = await repo.save(AsyncOrderTestModel(name='Second', priority=2))
    item3 = await repo.save(AsyncOrderTestModel(name='Third', priority=3))
    
    return {
        'repo': repo,
        'item1': item1,
        'item2': item2,
        'item3': item3,
    }
```

---

## よくある問題と解決策

### 問題1: 非同期フィクスチャで autouse=True エラー

**エラー内容:**
```
PytestRemovedIn9Warning: 'test_xxx' requested an async fixture 'setup_method' 
with autouse=True, with no plugin or hook that handled it.
```

**原因:**  
pytest-asyncio は autouse=True の非同期フィクスチャをサポートしていない。

**解決策:**
```python
# ❌ autouse=True は使えない
@pytest.fixture(autouse=True)
async def setup_method(async_db_test):
    # ...

# ✅ autouse=False（デフォルト）で明示的に指定
@pytest.fixture
async def setup_method(async_db_test):
    # ...

# テストで明示的に受け取る
@pytest.mark.asyncio
async def test_find(self, setup_method):
    data = await setup_method
    results = await data['repo'].find()
```

### 問題2: フィクスチャのデータが他のテストに影響

**症状:**  
あるテストがデータを変更すると、他のテストが失敗する。

**原因:**  
scope='class' や scope='module' で同じデータを共有している。

**解決策:**
```python
# ✅ scope='function'（デフォルト）を使う
@pytest.fixture
def setup_users(db_test):  # scope指定なし = function
    """各テストで新しいデータを作成"""
    # ...

# または Transaction Rollback を使う（repom のデフォルト）
@pytest.fixture
def db_test(db_engine):
    """各テストでトランザクションをロールバック"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    transaction.rollback()  # テスト後にロールバック
    connection.close()
```

### 問題3: フィクスチャが複雑になりすぎる

**症状:**  
1つのフィクスチャで多くのデータを作成している。

**解決策:**  
複数のフィクスチャに分割する。

```python
# ✅ 目的別にフィクスチャを分割
@pytest.fixture
def setup_users(db_test):
    """基本的なユーザーデータ"""
    repo = UserRepository(session=db_test)
    users = [repo.save(User(name=f'User{i}')) for i in range(3)]
    return {'repo': repo, 'users': users}

@pytest.fixture
def setup_posts(setup_users):
    """ユーザーフィクスチャに依存する投稿データ"""
    post_repo = PostRepository(session=setup_users['repo'].session)
    posts = []
    for user in setup_users['users']:
        post = post_repo.save(Post(title='Test', author_id=user.id))
        posts.append(post)
    return {'post_repo': post_repo, 'posts': posts}

@pytest.fixture
def setup_full_data(setup_users, setup_posts):
    """全データをまとめたフィクスチャ"""
    return {
        **setup_users,
        **setup_posts,
    }
```

---

## 参考リンク

- [pytest fixtures 公式ドキュメント](https://docs.pytest.org/en/stable/fixture.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [repom testing_guide.md](testing_guide.md)

---

## 実装例

repom のテストで実際に使用しているフィクスチャパターン：

- [tests/conftest.py](../../tests/conftest.py) - 共通フィクスチャ定義
- [tests/unit_tests/test_repository_default_order_by.py](../../tests/unit_tests/test_repository_default_order_by.py) - 同期フィクスチャの使用例
- [tests/unit_tests/test_async_repository_default_order_by.py](../../tests/unit_tests/test_async_repository_default_order_by.py) - 非同期フィクスチャの使用例
