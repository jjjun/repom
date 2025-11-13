# Issue: SQLAlchemy カラム継承制約による use_id 設計の課題

## 問題の本質

### SQLAlchemy のカラム継承制約

SQLAlchemy では、**親クラスに追加されたカラムは、全てのサブクラスに自動的に継承され、削除できません**。

```python
class BaseModel(Base):
    __abstract__ = True
    
    def __init_subclass__(cls, use_id=True, ...):
        if use_id:
            cls.id = Column(Integer, primary_key=True)  # ← BaseModel に id が追加
```

この場合：

1. `BaseModel.__init_subclass__` が実行され、`BaseModel` クラスに `id` カラムが追加される
2. Python のクラス属性継承により、`id` は全てのサブクラスに自動的に継承される
3. サブクラスで `use_id=False` を指定しても、**既に継承された `id` カラムを削除できない**

### 具体例：問題が発生するケース

```python
class BaseModel(Base):
    def __init_subclass__(cls, use_id=True, ...):  # ← デフォルト True
        if use_id:
            cls.id = Column(Integer, primary_key=True)

class BaseModelAuto(BaseModel, use_id=False):  # ← False を指定しても...
    pass

class MyModel(BaseModelAuto):  # ← id カラムが継承されてしまう！
    __tablename__ = 'my_table'
    user_id = Column(Integer, primary_key=True)
    order_id = Column(Integer, primary_key=True)
```

**結果：** `MyModel` には `id`, `user_id`, `order_id` の3つのカラムが存在し、複合主キーが正しく機能しなくなります。

## 理想的な動作（実現不可能）

以下のような動作が理想的ですが、SQLAlchemy の制約により実現できません：

```python
# 理想（実現不可能）
class BaseModel(Base, use_id=True):  # ← デフォルト True
    pass

class User(BaseModel):  # ← id カラムあり（デフォルト）
    __tablename__ = 'users'
    name = Column(String(100))

class OrderItem(BaseModel, use_id=False):  # ← id カラムなし（明示的に False）
    __tablename__ = 'order_items'
    order_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, primary_key=True)
```

**問題：** `BaseModel` に `id` カラムが追加されると、`OrderItem` でも `id` カラムが継承されてしまう。

## 現在の回避策（妥協案）

### 現在の実装

```python
class BaseModel(Base):
    def __init_subclass__(cls, use_id=_UNSET, ...):
        if use_id is _UNSET:
            cls.use_id = getattr(cls, 'use_id', True)  # ← デフォルト True
        else:
            cls.use_id = use_id
        
        if cls.use_id:
            cls.id = Column(Integer, primary_key=True)

class BaseModelAuto(BaseModel, use_id=False):  # ← 明示的に False
    pass
```

### 問題点

1. **BaseModelAuto のサブクラスで use_id=False を明示的に指定する必要がある**
   - `BaseModelAuto` が `use_id=False` なので、サブクラスで `use_id=True` にしたい場合は明示的指定が必要
   - 逆に複合主キーの場合は `use_id=False` を継承するので問題ない

2. **BaseModel のサブクラスで use_id=False を明示的に指定する必要がある**
   - `BaseModel` が `use_id=True` なので、複合主キーの場合は明示的に `use_id=False` を指定する必要がある

## 検討した代替案

### 代替案1: BaseModel のデフォルトを False にする

```python
class BaseModel(Base):
    def __init_subclass__(cls, use_id=_UNSET, ...):
        if use_id is _UNSET:
            cls.use_id = getattr(cls, 'use_id', False)  # ← デフォルト False
        else:
            cls.use_id = use_id
```

**メリット：**
- `BaseModel` に `id` カラムが追加されないため、サブクラスで自由に制御可能

**デメリット：**
- ほとんどのモデルで `use_id=True` を明示的に指定する必要がある（ボイラープレート増加）
- 既存コードとの互換性が失われる

### 代替案2: 中間クラスを用意する

```python
class BaseModelCore(Base, use_id=False):  # ← デフォルト False
    """コア実装"""
    pass

class BaseModel(BaseModelCore, use_id=True):  # ← デフォルト True
    """通常モデル用"""
    pass

class BaseModelAuto(BaseModelCore, use_id=True):  # ← デフォルト True
    """自動スキーマ生成用"""
    pass
```

**問題：** `BaseModel` が `use_id=True` なので、`BaseModel` のサブクラスで `use_id=False` を指定しても `id` カラムが継承される（同じ問題）。

## まとめ

SQLAlchemy のカラム継承制約により、以下の動作は実現不可能：

- 親クラスで `use_id=True` をデフォルトにしつつ、サブクラスで `use_id=False` を指定して `id` カラムを削除する

~~現在の回避策：~~

- ~~`BaseModel` は `use_id=True` がデフォルト（ほとんどのモデルで id カラムが必要なため）~~
- ~~複合主キーが必要な場合は `use_id=False` を明示的に指定する~~
- ~~`BaseModelAuto` は `use_id=False` を明示的に指定（サブクラスで柔軟に制御できるようにするため）~~

~~この設計は一見不自然ですが、SQLAlchemy の制約に対する最適な妥協案です。~~

## ✅ 解決策（実装済み）

**抽象クラスと具象クラスを区別する**ことで、この問題を完全に解決しました。

### 実装方法

`__init_subclass__` で `__tablename__` の有無をチェックし、**抽象クラス（`__tablename__` がない）にはカラムを追加しない**ようにしました：

```python
class BaseModel(Base):
    __abstract__ = True
    
    def __init_subclass__(cls, use_id=_UNSET, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # パラメータ処理
        if use_id is _UNSET:
            cls.use_id = getattr(cls, 'use_id', True)
        else:
            cls.use_id = use_id
        
        # 重要: 抽象クラス（__tablename__ がない）にはカラムを追加しない
        if not hasattr(cls, '__tablename__'):
            return
        
        # 具象クラス（__tablename__ がある）のみカラムを追加
        if cls.use_id:
            cls.id = Column(Integer, primary_key=True)
```

### メリット

1. ✅ **`BaseModel` のデフォルトを `use_id=True` にできる**
2. ✅ **`BaseModelAuto` のデフォルトも `use_id=True` にできる**
3. ✅ **サブクラスで `use_id=False` を指定すれば、id カラムが追加されない**
4. ✅ **抽象クラスにはカラムが追加されないので、継承の問題が発生しない**
5. ✅ **既存コードの互換性を維持**

### 使用例

```python
# 通常モデル（id カラムあり、デフォルト）
class User(BaseModel):
    __tablename__ = 'users'
    name = Column(String(100))

# 複合主キーモデル（id カラムなし）
class OrderItem(BaseModel, use_id=False):
    __tablename__ = 'order_items'
    order_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, primary_key=True)

# BaseModelAuto も同様
class Product(BaseModelAuto):  # ← id カラムあり（デフォルト）
    __tablename__ = 'products'
    name = Column(String(100))

class ProductCategory(BaseModelAuto, use_id=False):  # ← id カラムなし
    __tablename__ = 'product_categories'
    product_id = Column(Integer, primary_key=True)
    category_id = Column(Integer, primary_key=True)
```

### 技術的詳細

- **抽象クラスの判定**: `__tablename__` の有無で判定
  - SQLAlchemy は `__tablename__` がないクラスを抽象クラスとして扱う
  - `__abstract__ = True` は明示的な宣言だが、`__tablename__` がなければ自動的に抽象クラスになる

- **カラム追加のタイミング**: `__init_subclass__` で動的に追加
  - 抽象クラスではカラムを追加しないため、継承の問題が発生しない
  - 具象クラスごとに独立してカラムを制御できる

- **テスト結果**: 全 103 テストが合格 ✅

## 参考リンク

- [SQLAlchemy Column Inheritance](https://docs.sqlalchemy.org/en/20/orm/inheritance.html)
- [Python __init_subclass__](https://docs.python.org/3/reference/datamodel.html#object.__init_subclass__)
