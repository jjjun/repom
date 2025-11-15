# システムカラムとカスタム型ガイド

## 概要

repom では、`BaseModel` を通じて自動的に追加されるシステムカラムと、それらに使用されるカスタム型を提供しています。このガイドでは、各カラムの仕様、動作、注意点を詳しく説明します。

---

## システムカラム

### 1. `id` カラム

**型**: `Integer` (primary key, autoincrement)

**追加条件**: `use_id=True` (デフォルト)

**仕様**:
```python
class BaseModel(DeclarativeBase):
    def __init_subclass__(cls, use_id=_UNSET, ...):
        if cls.use_id:
            cls.id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

**動作**:
- データベース保存時に自動的に採番される（autoincrement）
- Python オブジェクト作成時点では `None`
- `session.add()` + `session.commit()` 後に値が設定される

**使用例**:
```python
class User(BaseModel):
    __tablename__ = 'users'
    # use_id=True がデフォルト
    
    name: Mapped[str] = mapped_column(String(100))

user = User(name='Alice')
print(user.id)  # None（まだDB保存していない）

session.add(user)
session.commit()
print(user.id)  # 1（DB保存後に採番される）
```

**無効化する場合**:
```python
class UserSession(BaseModel, use_id=False):
    __tablename__ = 'user_sessions'
    
    # Composite primary key を使用
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), primary_key=True)
```

**注意点**:
- ⚠️ **テストでのモック**: DB に保存しない場合、`id` は `None` のまま
- ⚠️ **Pydantic バリデーション**: `get_response_schema()` で生成されるスキーマは `id: int` を期待
  - テストで DB に保存しない場合は、手動で `obj.id = 1` のように設定が必要

---

### 2. `created_at` カラム

**型**: `AutoDateTime` (カスタム型)

**追加条件**: `use_created_at=True` (デフォルト)

**仕様**:
```python
class BaseModel(DeclarativeBase):
    def __init_subclass__(cls, use_created_at=_UNSET, ...):
        if cls.use_created_at:
            cls.created_at: Mapped[datetime] = mapped_column(AutoDateTime)
```

**動作**:
- **データベース保存時**に自動的に `datetime.now()` が設定される
- Python オブジェクト作成時点では `None`（これは仕様）
- `session.add()` + `session.commit()` 後に値が設定される

**AutoDateTime の実装**:
```python
class AutoDateTime(TypeDecorator):
    impl = DateTime
    
    def process_bind_param(self, value, dialect):
        """データベース保存時に実行される"""
        if value is None:
            value = datetime.now()  # ← ここで自動設定
        return value
    
    def process_result_value(self, value, dialect):
        """データベース読み取り時に実行される"""
        return value
```

**使用例**:
```python
from datetime import datetime

class Article(BaseModel):
    __tablename__ = 'articles'
    # use_created_at=True がデフォルト
    
    title: Mapped[str] = mapped_column(String(200))

# ケース1: 自動設定（推奨）
article = Article(title='Hello World')
print(article.created_at)  # None（まだDB保存していない）

session.add(article)
session.commit()
print(article.created_at)  # 2025-11-15 10:30:45.123456（DB保存時に自動設定）

# ケース2: 手動設定（過去の日時を記録する場合など）
past_date = datetime(2024, 1, 1, 0, 0, 0)
article2 = Article(title='Old Article', created_at=past_date)
session.add(article2)
session.commit()
print(article2.created_at)  # 2024-01-01 00:00:00（手動設定した値が使われる）
```

**重要な仕様**:
- ✅ **意図的な設計**: `created_at` は「**データベース保存時の時刻**」を記録するため
- ✅ **Python オブジェクトの作成時刻ではない**: オブジェクトを作成してから保存までの時間が空いても問題ない
- ✅ **データの整合性**: DB に保存された時刻を正確に記録できる

**無効化する場合**:
```python
class TempModel(BaseModel, use_created_at=False):
    __tablename__ = 'temp_models'
    # created_at カラムは追加されない
```

**注意点**:
- ⚠️ **テストでのモック**: DB に保存しない場合、`created_at` は `None` のまま
  ```python
  # ❌ テストで失敗する例
  book = BookModel(title='Test')
  book.id = 1  # 手動設定
  response_data = book.to_dict()
  # response_data['created_at'] は None
  # Pydantic バリデーションでエラー
  
  # ✅ 正しいテスト方法
  book = BookModel(title='Test')
  session.add(book)
  session.commit()  # ← DB に保存
  response_data = book.to_dict()
  # response_data['created_at'] は datetime オブジェクト
  ```

- ⚠️ **Pydantic スキーマとの整合性**: `get_response_schema()` で生成されるスキーマは `created_at: datetime` を期待
  - テストで DB に保存しない場合は、スキーマを `created_at: Optional[datetime]` にするか、手動で値を設定

---

### 3. `updated_at` カラム

**型**: `AutoDateTime` (カスタム型)

**追加条件**: `use_updated_at=True` (デフォルト)

**仕様**:
```python
class BaseModel(DeclarativeBase):
    def __init_subclass__(cls, use_updated_at=_UNSET, ...):
        if cls.use_updated_at:
            cls.updated_at: Mapped[datetime] = mapped_column(AutoDateTime)
```

**動作**:
- **データベース保存時**に自動的に `datetime.now()` が設定される（`created_at` と同じ）
- **更新時**に自動的に `datetime.now()` が設定される（SQLAlchemy Event で実装）
- Python オブジェクト作成時点では `None`

**自動更新の実装** (BaseModel):
```python
@event.listens_for(BaseModel, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    """モデル更新時に updated_at を自動更新"""
    if hasattr(target, 'updated_at'):
        target.updated_at = datetime.now()
```

**使用例**:
```python
from datetime import datetime
import time

class Product(BaseModel):
    __tablename__ = 'products'
    # use_created_at=True, use_updated_at=True がデフォルト
    
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)

# 新規作成
product = Product(name='Laptop', price=1000)
session.add(product)
session.commit()

print(product.created_at)  # 2025-11-15 10:30:00.000000
print(product.updated_at)  # 2025-11-15 10:30:00.000000（初回は created_at と同じ）

# 少し待ってから更新
time.sleep(2)

product.price = 900
session.commit()

print(product.created_at)  # 2025-11-15 10:30:00.000000（変わらない）
print(product.updated_at)  # 2025-11-15 10:30:02.000000（更新された）
```

**重要な仕様**:
- ✅ **自動更新**: `session.commit()` 時に SQLAlchemy Event が発火し、自動的に更新される
- ✅ **created_at との関係**: 初回保存時は `created_at` と同じ値、更新時のみ変わる
- ✅ **手動設定も可能**: 必要に応じて手動で `updated_at` を設定できる

**無効化する場合**:
```python
class StaticModel(BaseModel, use_updated_at=False):
    __tablename__ = 'static_models'
    # updated_at カラムは追加されない
```

**注意点**:
- ⚠️ **created_at と同じ制約**: DB に保存しない場合、`updated_at` は `None` のまま
- ⚠️ **bulk update では発火しない**: `session.query(Model).update({...})` では Event が発火しないため、手動で設定が必要
  ```python
  # ❌ bulk update では updated_at が更新されない
  session.query(Product).filter_by(category='old').update({'price': 500})
  
  # ✅ 手動で updated_at を設定
  session.query(Product).filter_by(category='old').update({
      'price': 500,
      'updated_at': datetime.now()
  })
  ```

---

## カスタム型

### AutoDateTime

**実装ファイル**: `repom/custom_types/AutoDateTime.py`

**目的**: データベース保存時に自動的に現在時刻を設定する

**完全な実装**:
```python
from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime

class AutoDateTime(TypeDecorator):
    """
    Custom SQLAlchemy type to automatically set datetime values on insert.
    
    自動的に日時を設定するカスタム型:
    - 引数に何も渡されなければ、`datetime.now()` の値が入る事を保証
    - 引数に日付が渡されれば、その値が使われる事を保証
    
    使用例:
        created_at = mapped_column(AutoDateTime, nullable=False)
        updated_at = mapped_column(AutoDateTime, nullable=False)
    
    注意:
        updated_at の自動更新は SQLAlchemy Event で実装されています
        （BaseModel の @event.listens_for を参照）
    """
    
    impl = DateTime
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化
    
    def process_bind_param(self, value, dialect):
        """データベースへ保存する前に実行される"""
        if value is None:
            value = datetime.now()
        return value
    
    def process_result_value(self, value, dialect):
        """データベースから読み取った後に実行される"""
        return value
```

**実行タイミング**:

| タイミング | `process_bind_param` | `process_result_value` |
|-----------|---------------------|----------------------|
| Python → DB | ✅ 実行される | ❌ 実行されない |
| DB → Python | ❌ 実行されない | ✅ 実行される |
| オブジェクト作成 | ❌ 実行されない | ❌ 実行されない |

**重要**: Python オブジェクトを作成しただけでは `process_bind_param` は実行されない

**使用例**:
```python
from repom.custom_types.AutoDateTime import AutoDateTime
from datetime import datetime

class Event(BaseModel):
    __tablename__ = 'events'
    use_created_at = False  # システムカラムは使わない
    
    name: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(AutoDateTime)  # カスタムで使用

# 自動設定
event1 = Event(name='System Start')
print(event1.occurred_at)  # None（まだDB保存していない）

session.add(event1)
session.commit()
print(event1.occurred_at)  # 2025-11-15 10:30:00.000000（DB保存時に自動設定）

# 手動設定（過去のイベントを記録）
past_time = datetime(2024, 12, 31, 23, 59, 59)
event2 = Event(name='Old Event', occurred_at=past_time)
session.add(event2)
session.commit()
print(event2.occurred_at)  # 2024-12-31 23:59:59（手動設定した値が使われる）
```

---

## テストでの注意点

### 問題: Pydantic バリデーションエラー

**症状**:
```python
def test_book_response():
    book = BookModel(title='Test', author_id=1, price=1000)
    book.id = 1  # 手動設定
    
    BookResponse = BookModel.get_response_schema()
    response_data = book.to_dict()
    
    # ❌ ValidationError: created_at should be a valid datetime, got None
    validated = BookResponse(**response_data)
```

**原因**:
- `book` を DB に保存していないため、`created_at` は `None`
- `get_response_schema()` で生成される Pydantic スキーマは `created_at: datetime` を期待

**解決策**:

#### 解決策1: DB に保存してからテストする（推奨）
```python
def test_book_response(session):  # session fixture を使用
    book = BookModel(title='Test', author_id=1, price=1000)
    
    session.add(book)
    session.commit()  # ← DB に保存
    
    BookResponse = BookModel.get_response_schema()
    response_data = book.to_dict()
    
    # ✅ created_at に datetime が設定されている
    validated = BookResponse(**response_data)
    assert validated.created_at is not None
```

#### 解決策2: 手動で値を設定する
```python
def test_book_response():
    from datetime import datetime
    
    book = BookModel(title='Test', author_id=1, price=1000)
    book.id = 1
    book.created_at = datetime.now()  # ← 手動設定
    
    BookResponse = BookModel.get_response_schema()
    response_data = book.to_dict()
    
    # ✅ 手動設定した値が使われる
    validated = BookResponse(**response_data)
    assert validated.created_at is not None
```

#### 解決策3: スキーマを Optional にする（非推奨）
```python
class BookModel(BaseModelAuto):
    __tablename__ = 'books'
    
    @BaseModelAuto.response_field(
        created_at=Optional[datetime]  # ← Optional にする
    )
    def to_dict(self):
        return super().to_dict()
```

**推奨**: 解決策1（DB に保存してテスト）を使用することで、実際の動作に近いテストができます。

---

## システムカラムの組み合わせ

### パターン1: すべて有効（デフォルト）
```python
class User(BaseModel):
    __tablename__ = 'users'
    # use_id=True, use_created_at=True, use_updated_at=True（デフォルト）
    
    name: Mapped[str] = mapped_column(String(100))

# 結果: id, created_at, updated_at が自動追加
```

### パターン2: id のみ無効
```python
class UserSession(BaseModel, use_id=False):
    __tablename__ = 'user_sessions'
    # use_created_at=True, use_updated_at=True（デフォルト）
    
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), primary_key=True)

# 結果: created_at, updated_at のみ追加
```

### パターン3: タイムスタンプのみ無効
```python
class StaticData(BaseModel, use_created_at=False, use_updated_at=False):
    __tablename__ = 'static_data'
    # use_id=True（デフォルト）
    
    key: Mapped[str] = mapped_column(String(50), unique=True)
    value: Mapped[str] = mapped_column(String(255))

# 結果: id のみ追加
```

### パターン4: すべて無効
```python
class CustomModel(BaseModel, use_id=False, use_created_at=False, use_updated_at=False):
    __tablename__ = 'custom_models'
    
    custom_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data: Mapped[str] = mapped_column(String(255))

# 結果: システムカラムなし（すべて手動定義）
```

---

## ベストプラクティス

### 1. デフォルト設定を活用する

**推奨**: ほとんどのモデルではデフォルト設定（id, created_at, updated_at すべて有効）を使用
```python
class Product(BaseModel):
    __tablename__ = 'products'
    # デフォルトのまま（何も指定しない）
    
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)
```

### 2. 複合主キーの場合のみ use_id=False

**use_id=False を使うべきケース**:
- 複合主キー（Composite Primary Key）を使用する場合
- 外部システムの ID を主キーとして使用する場合

```python
class OrderItem(BaseModel, use_id=False):
    __tablename__ = 'order_items'
    
    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)
```

### 3. テストでは DB に保存する

**推奨**: テストで Pydantic バリデーションを行う場合は、DB に保存してから実施
```python
def test_user_response_schema(session):
    user = User(name='Alice', email='alice@example.com')
    
    # DB に保存
    session.add(user)
    session.commit()
    
    # レスポンススキーマでバリデーション
    UserResponse = User.get_response_schema()
    validated = UserResponse(**user.to_dict())
    
    assert validated.id > 0
    assert validated.created_at is not None
```

### 4. 手動で過去の日時を記録する場合

**use case**: データ移行やバックフィルで過去の日時を記録する場合
```python
from datetime import datetime

# 2024年のデータを移行
old_data = User(
    name='Bob',
    created_at=datetime(2024, 1, 1, 0, 0, 0),
    updated_at=datetime(2024, 1, 1, 0, 0, 0)
)
session.add(old_data)
session.commit()
```

### 5. システムカラムの保護

**重要**: `id`, `created_at`, `updated_at` は **読み取り専用** として扱う

```python
# ❌ 避けるべき（システムカラムの手動更新）
user.id = 999
user.created_at = datetime.now()

# ✅ 推奨（データ移行時のみ例外的に許可）
# 通常の業務ロジックではシステムカラムを変更しない
```

---

## FAQ

### Q1: `created_at` が None のままなのはバグですか？

**A**: いいえ、仕様です。`created_at` は **データベース保存時の時刻** を記録するため、Python オブジェクトを作成しただけでは `None` です。`session.commit()` 後に値が設定されます。

### Q2: テストで DB に保存せずに `created_at` を使いたい

**A**: 手動で値を設定してください：
```python
book.created_at = datetime.now()
```
ただし、実際の動作に近づけるため、可能な限り DB に保存してテストすることを推奨します。

### Q3: `updated_at` が更新されない

**A**: 以下を確認してください：
1. `session.commit()` を呼んでいるか？
2. bulk update（`query.update()`）を使っていないか？
3. `use_updated_at=True` になっているか？

### Q4: システムカラムを後から追加/削除できますか？

**A**: できません。`use_id`, `use_created_at`, `use_updated_at` はクラス定義時に決定され、後から変更できません。必要に応じて Alembic でマイグレーションを作成してください。

### Q5: 他のカスタム型はありますか？

**A**: はい。以下のカスタム型が用意されています：
- `AutoDateTime`: 自動的に現在時刻を設定
- `ISO8601DateTime`: ISO8601 形式の文字列として保存
- `ISO8601DateTimeStr`: ISO8601 文字列として読み書き
- `JSONEncoded`: JSON として保存
- `ListJSON`: リストを JSON として保存
- `StrEncodedArray`: カンマ区切り文字列として保存

詳細は各カスタム型のドキュメントを参照してください。

---

## 関連ドキュメント

- **BaseModel**: `repom/base_model.py`
- **BaseModelAuto**: `repom/base_model_auto.py`
- **AutoDateTime**: `repom/custom_types/AutoDateTime.py`
- **Repository ガイド**: `docs/guides/repository_and_utilities_guide.md`
- **BaseModelAuto ガイド**: `docs/guides/base_model_auto_guide.md`

---

**作成日**: 2025-11-15  
**最終更新**: 2025-11-15  
**関連 Issue**: #006 (SQLAlchemy 2.0 migration)
