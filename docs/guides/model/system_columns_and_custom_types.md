# システムカラムとカスタム型ガイド

## 概要

repom の `BaseModel` は、オプトインでシステムカラムを自動追加できます。このガイドでは、各カラムの仕様と使い方を説明します。

**デフォルト設定**:
- `use_id=True` - 整数型の主キー `id` を追加（デフォルト）
- `use_uuid=False` - UUID型の主キー（use_id と排他）
- `use_created_at=False` - 作成日時カラム（デフォルトで無効）
- `use_updated_at=False` - 更新日時カラム（デフォルトで無効）

---

## システムカラム

### 1. `id` カラム（整数型）

**型**: `Integer` (primary key, autoincrement)  
**デフォルト**: 有効（`use_id=True`）

**動作**:
- データベース保存時に自動採番
- オブジェクト作成時は `None`、`session.commit()` 後に値が設定される

**使用例**:
```python
class User(BaseModel):
    __tablename__ = 'users'
    # use_id=True がデフォルトなので指定不要
    
    name: Mapped[str] = mapped_column(String(100))

user = User(name='Alice')
print(user.id)  # None

session.add(user)
session.commit()
print(user.id)  # 1
```

**無効化**（複合主キーの場合）:
```python
class UserSession(BaseModel, use_id=False):
    __tablename__ = 'user_sessions'
    
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), primary_key=True)
```

---

### 2. `id` カラム（UUID型）

**型**: `String(36)` (primary key, UUID v4)  
**デフォルト**: 無効（`use_uuid=False`）

**排他制御**: `use_uuid=True` と `use_id=True` は同時指定不可

**動作**:
- オブジェクト作成時に UUID v4 を自動生成
- 36文字のハイフン付き文字列（例: `550e8400-e29b-41d4-a716-446655440000`）
- カラム名は `id`（BaseRepository 互換）

**使用例**:
```python
class User(BaseModel, use_uuid=True):
    __tablename__ = 'users'
    # use_id は自動的に False になる
    
    name: Mapped[str] = mapped_column(String(100))

user = User(name='Alice')
print(user.id)  # '550e8400-e29b-41d4-a716-446655440000'
print(len(user.id))  # 36
```

**外部キー参照**:
```python
class Post(BaseModel, use_uuid=True):
    __tablename__ = 'posts'
    
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(200))
```

**使い分け**:
- 分散システム、マイクロサービス → UUID
- 単一サーバー、シンプルなアプリ → Integer
- 公開APIでIDを推測されたくない → UUID

---

### 3. `created_at` カラム

**型**: `AutoDateTime` (カスタム型)  
**デフォルト**: 無効（`use_created_at=False`）

**動作**:
- データベース保存時に `datetime.now()` を自動設定
- オブジェクト作成時は `None`、`session.commit()` 後に値が設定される
- 手動で過去の日時を指定することも可能

**有効化と使用例**:
```python
class Article(BaseModel, use_created_at=True):
    __tablename__ = 'articles'
    
    title: Mapped[str] = mapped_column(String(200))

# 自動設定
article = Article(title='Hello')
print(article.created_at)  # None

session.add(article)
session.commit()
print(article.created_at)  # 2025-12-25 10:30:45.123456

# 手動設定（データ移行時など）
from datetime import datetime
old_article = Article(title='Old', created_at=datetime(2024, 1, 1))
session.add(old_article)
session.commit()
print(old_article.created_at)  # 2024-01-01 00:00:00
```

---

### 4. `updated_at` カラム

**型**: `AutoDateTime` (カスタム型)  
**デフォルト**: 無効（`use_updated_at=False`）

**動作**:
- データベース保存時に `datetime.now()` を自動設定
- 更新時に SQLAlchemy Event で自動更新
- 初回保存時は `created_at` と同じ値、更新時のみ変わる

**有効化と使用例**:
```python
class Product(BaseModel, use_created_at=True, use_updated_at=True):
    __tablename__ = 'products'
    
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)

product = Product(name='Laptop', price=1000)
session.add(product)
session.commit()

print(product.created_at)  # 2025-12-25 10:30:00
print(product.updated_at)  # 2025-12-25 10:30:00（初回は同じ）

# 更新
product.price = 900
session.commit()

print(product.created_at)  # 2025-12-25 10:30:00（変わらない）
print(product.updated_at)  # 2025-12-25 10:30:05（自動更新）
```

**注意**: bulk update（`query.update()`）では自動更新されません。手動で設定してください：
```python
from datetime import datetime

session.query(Product).filter_by(category='old').update({
    'price': 500,
    'updated_at': datetime.now()  # 手動設定
})
```

---

## カスタム型: AutoDateTime

**実装**: `repom/custom_types/AutoDateTime.py`

**目的**: データベース保存時に自動的に現在時刻を設定

**実装**:
```python
from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime

class AutoDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """DB保存時に実行"""
        if value is None:
            value = datetime.now()
        return value
    
    def process_result_value(self, value, dialect):
        """DB読み取り時に実行"""
        return value
```

**重要**: オブジェクト作成時には実行されません。`session.commit()` で DB 保存時にのみ実行されます。

---

## システムカラムの組み合わせパターン

### パターン1: ID のみ（デフォルト）
```python
class User(BaseModel):
    __tablename__ = 'users'
    # use_id=True のみ（デフォルト）
    
    name: Mapped[str] = mapped_column(String(100))
```

### パターン2: ID + タイムスタンプ
```python
class Article(BaseModel, use_created_at=True, use_updated_at=True):
    __tablename__ = 'articles'
    # use_id=True はデフォルトで有効
    
    title: Mapped[str] = mapped_column(String(200))
```

### パターン3: UUID + タイムスタンプ
```python
class User(BaseModel, use_uuid=True, use_created_at=True, use_updated_at=True):
    __tablename__ = 'users'
    # use_id は自動的に False
    
    name: Mapped[str] = mapped_column(String(100))
```

### パターン4: 複合主キー + タイムスタンプ
```python
class UserSession(BaseModel, use_id=False, use_created_at=True):
    __tablename__ = 'user_sessions'
    
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), primary_key=True)
```

### パターン5: システムカラムなし
```python
class CustomModel(BaseModel, use_id=False):
    __tablename__ = 'custom_models'
    
    custom_id: Mapped[str] = mapped_column(String(36), primary_key=True)
```

---

## テストでの注意点

### 問題: created_at が None でバリデーションエラー

**症状**:
```python
book = BookModel(title='Test', price=1000)
book.id = 1  # 手動設定

BookResponse = BookModel.get_response_schema()
# ValidationError: created_at should be a valid datetime, got None
validated = BookResponse(**book.to_dict())
```

**原因**: DB に保存していないため、`created_at` は `None` のまま

**解決策1**: DB に保存する（推奨）
```python
def test_book_response(session):
    book = BookModel(title='Test', price=1000)
    session.add(book)
    session.commit()  # これで created_at に値が入る
    
    validated = BookResponse(**book.to_dict())
    assert validated.created_at is not None
```

**解決策2**: 手動で値を設定
```python
from datetime import datetime

book = BookModel(title='Test', price=1000)
book.id = 1
book.created_at = datetime.now()  # 手動設定

validated = BookResponse(**book.to_dict())
```

---

## ベストプラクティス

### 1. デフォルト設定で十分か判断する

**ID のみで十分な場合**（多くのケース）:
```python
class Product(BaseModel):
    __tablename__ = 'products'
    # デフォルト設定をそのまま使う
```

**タイムスタンプが必要な場合**:
```python
class Article(BaseModel, use_created_at=True, use_updated_at=True):
    __tablename__ = 'articles'
```

### 2. 複合主キーの場合は use_id=False

```python
class OrderItem(BaseModel, use_id=False, use_created_at=True):
    __tablename__ = 'order_items'
    
    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

### 3. テストでは DB に保存する

Pydantic バリデーションを行う場合は、必ず DB に保存してからテストしてください。

### 4. システムカラムは読み取り専用

```python
# ❌ 避ける
user.id = 999
user.created_at = datetime.now()

# ✅ データ移行時のみ例外的に許可
```

---

## FAQ

### Q1: created_at が None のままなのはバグですか？

**A**: いいえ、仕様です。`created_at` はデータベース保存時の時刻を記録します。オブジェクト作成時は `None` で、`session.commit()` 後に値が設定されます。

### Q2: デフォルトで created_at を有効にできますか？

**A**: できません。repom のデフォルト設定は `use_created_at=False` です。必要に応じて明示的に `use_created_at=True` を指定してください。

### Q3: updated_at が更新されない

**A**: 以下を確認してください：
1. `session.commit()` を呼んでいるか
2. bulk update（`query.update()`）を使っていないか（自動更新されません）
3. `use_updated_at=True` を指定しているか

### Q4: use_id と use_uuid を両方 True にしたい

**A**: できません。排他制御されています。どちらか一方のみ使用してください。

### Q5: 他のカスタム型はありますか？

**A**: はい。以下が用意されています：
- `ISO8601DateTime`: ISO8601 形式の文字列として保存
- `JSONEncoded`: JSON として保存
- `ListJSON`: リストを JSON として保存
- `StrEncodedArray`: カンマ区切り文字列として保存

詳細は各カスタム型のソースコードを参照してください。

---

## 関連ドキュメント

- [BaseModel](../../repom/base_model.py)
- [BaseModelAuto ガイド](../base_model_auto_guide.md)
- [Repository ガイド](../repository/repository_and_utilities_guide.md)

---

**最終更新**: 2025-12-25  
**関連コミット**: FastAPI Depends compatibility fix
    
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
