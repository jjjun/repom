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
        
        results = repo.find(limit=100)
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
        results = setup_users['repo'].find(limit=100)
        assert len(results) == 3
    
    def test_get_user_by_id(self, setup_users):
        """同じフィクスチャを別のテストでも使用"""
        user = setup_users['repo'].get_by_id(setup_users['user1'].id)
        assert user.name == 'Alice'
    
    def test_filter_by_age(self, setup_users):
        """フィクスチャのデータを利用した検索テスト"""
        results = setup_users['repo'].find(filters=[User.age >= 30], limit=100)
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
import pytest_asyncio
from repom import AsyncBaseRepository

@pytest_asyncio.fixture
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
        data = setup_users
        results = await data['repo'].find(limit=100)
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, setup_users):
        data = setup_users
        user = await data['repo'].get_by_id(data['user1'].id)
        assert user.name == 'Alice'
```

### 非同期フィクスチャの定義

`async def` フィクスチャには `@pytest_asyncio.fixture` を使います。`autouse=True` も
利用できます。通常の `@pytest.fixture` では非同期フィクスチャを処理できず、pytest 9
ではエラーになります。

```python
import pytest_asyncio

# ✅ autouse=True も使用可能
@pytest_asyncio.fixture(autouse=True)
async def setup_method(async_db_test):
    repo = AsyncUserRepository(session=async_db_test)
    # ...
    return repo
```

**理由:**
- `pytest_asyncio.fixture` が async fixture のセットアップ・teardown を管理する
- `autouse=True` は同期・非同期どちらの fixture でも指定できる

**解決策:**
- async fixture には `@pytest_asyncio.fixture` を使う
- fixture の値を引数で受け取ると、テスト内ではすでに解決済みなので `await` しない

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

### scope='class' / scope='module'

`db_test` は function scope なので、これに依存する class-scoped または module-scoped fixture は
pytest の `ScopeMismatch` になります。`db_test` を使う fixture は function scope にしてください。
複数 test でデータを共有する必要がある場合は、より広い scope の独立した transaction と cleanup を設計します。
`create_test_fixtures()` はその設計を提供しません。

### scope='session'

```python
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

**特徴:**
- `db_engine` は session scope、`db_test` は function scope の fixture
- schema 作成は factory が管理し、test ごとの rollback は `db_test` を通した書き込みが対象
- 他の session や connection からの書き込みが `db_test` の rollback に含まれる保証はない
- factory の実装と引数は [`repom/testing.py`](../../../repom/testing.py) を参照

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
    results = setup_users['repo'].find(limit=100)
    assert len(results) == 4  # admin + 3 users

# ❌ 悪い例：タプルだとインデックスが不明瞭
@pytest.fixture
def setup_users(db_test):
    return repo, admin_user, [user1, user2, user3]

def test_find_users(setup_users):
    results = setup_users[0].find(limit=100)  # 0 が何か分からない
```

### 3. フィクスチャは共通資産として扱う

共通 fixture の `tests/conftest.py` 用スニペットと DB の破壊的操作ガードは
[テストガイド](testing_guide.md)を参照してください。実装は
[`repom/testing.py`](../../../repom/testing.py)にあります。

### 4. docstring でフィクスチャの目的を明記

```python
@pytest_asyncio.fixture
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

### 問題1: 非同期フィクスチャの定義と取得

pytest 9 以降では、`@pytest.fixture` で定義した async fixture を要求するとエラーに
なります。`pytest-asyncio` を使う場合は `@pytest_asyncio.fixture` で定義します。

fixture の返り値は引数として受け取った時点で解決済みです。`await` しないでください。
```python
import pytest
import pytest_asyncio

# ✅ pytest_asyncio.fixture で定義
@pytest_asyncio.fixture
async def setup_method(async_db_test):
    # ...

@pytest.mark.asyncio
async def test_find(self, setup_method):
    data = setup_method
    results = await data['repo'].find(limit=100)
```

### 問題2: db_test と fixture scope の不一致

**症状:**  
class-scoped または module-scoped fixture が `db_test` に依存すると `ScopeMismatch` が発生する。

**原因:**  
`db_test` は function scope で、pytest はより広い scope の fixture から function-scoped fixture への依存を許可しない。

**解決策:**
```python
# ✅ scope='function'（デフォルト）を使う
@pytest.fixture
def setup_users(db_test):  # scope指定なし = function
    """各テストで新しいデータを作成"""
    # ...

```

別の広い scope の database/session 設計で test 間にデータを共有する場合は、cleanup を行い、共有データの変更が
他の test に影響しないようにしてください。`create_test_fixtures()` の `db_test` はその用途には使えません。

fixture factory と破壊的操作ガードの正本は[テストガイド](testing_guide.md)です。

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

- [tests/conftest.py](../../../tests/conftest.py) - 共通フィクスチャ定義
- [tests/unit_tests/test_repository_default_order_by.py](../../../tests/unit_tests/test_repository_default_order_by.py) - 同期フィクスチャの使用例
- [tests/unit_tests/test_async_fixtures.py](../../../tests/unit_tests/test_async_fixtures.py) - 非同期フィクスチャの使用例
