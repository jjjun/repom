# Annotation Inheritance の実装検証

## ステータス
- **段階**: 調査待ち
- **優先度**: 中
- **複雑度**: 中
- **作成日**: 2025-11-15
- **関連 Issue**: #006 (SQLAlchemy 2.0 migration)

## 概要

Issue #006 (Phase 1.1) で BaseModel の `__annotations__` 継承問題を修正したが、この実装が正しいのか、他の影響がないかを調査する必要がある。

## 背景

### 発見された問題

Issue #006 の Phase 1.1 で、以下の問題が発見された：

**症状**:
```python
class AutoModelWithoutId(BaseModelAuto, use_id=False):
    __tablename__ = 'test_table'

# ❌ 期待: id カラムなし
# ❌ 実際: id カラムが存在（親クラスから継承）
```

**原因**:
- `hasattr(cls, '__annotations__')` は継承されたアトリビュートも検出
- 親クラスの `__annotations__` が子クラスに継承され、意図しないカラムが追加

**適用された修正** (Commit: 964504d):
```python
# ❌ Before
if not hasattr(cls, '__annotations__'):
    cls.__annotations__ = {}

# ✅ After
if '__annotations__' not in cls.__dict__:
    cls.__annotations__ = {}
```

### 修正の意図

1. **継承を防ぐ**: 各クラスが独自の `__annotations__` を持つ
2. **動的カラム追加を正確に**: `use_id=False` などのオプションを正しく動作させる
3. **型ヒント整合性**: mypy/Pylance が正確な型を推論できるようにする

## 調査項目

### 1. Python の `__annotations__` 継承動作の確認

**疑問**:
- Python では通常、`__annotations__` はどう継承されるのか？
- クラスごとに新規作成するのは標準的なパターンか？
- 継承を意図的に使うべきケースはあるか？

**調査方法**:
```python
# テストコード例
class Parent:
    x: int

class Child(Parent):
    y: str

# 確認項目
print(Parent.__annotations__)  # {'x': <class 'int'>}
print(Child.__annotations__)   # {'y': <class 'str'>} or {'x': <class 'int'>, 'y': <class 'str'>}?
print('__annotations__' in Parent.__dict__)
print('__annotations__' in Child.__dict__)
```

**期待される結果**:
- 各クラスが独自の `__annotations__` を持つ
- 継承関係は `__mro__` で解決される

### 2. SQLAlchemy 2.0 の推奨パターンとの整合性

**疑問**:
- SQLAlchemy 2.0 のドキュメントではどう推奨されているか？
- `DeclarativeBase` や `MappedAsDataclass` との相性は？
- 動的カラム追加は推奨されているか？

**調査方法**:
- SQLAlchemy 2.0 公式ドキュメントを参照
- GitHub issues で類似の問題を検索
- SQLAlchemy のソースコードを確認

**参考 URL**:
- https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
- https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html

### 3. 他のフレームワークとの互換性

**疑問**:
- FastAPI で `BaseModel` を使った場合、問題はないか？
- Pydantic との相性は？（`get_response_schema()` 生成時）
- mypy/Pylance の型チェックは正確か？

**調査方法**:
```python
# FastAPI 統合テスト
from fastapi import FastAPI
from repom.base_model import BaseModel

class User(BaseModel):
    __tablename__ = 'users'
    name: Mapped[str] = mapped_column(String(100))

app = FastAPI()

@app.get("/users/{user_id}", response_model=???)
async def get_user(user_id: int):
    # BaseModel が正しく動作するか確認
    pass
```

### 4. エッジケースの検証

**疑問**:
- 多重継承の場合は？
- Mixin との組み合わせは？
- 既存の consuming project への影響は？

**テストケース**:
```python
# Case 1: 多重継承
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(AutoDateTime)

class User(BaseModel, TimestampMixin):
    pass

# Case 2: 既存の use_id/use_created_at との組み合わせ
class NoIdModel(BaseModel, use_id=False):
    pass

class NoTimestampsModel(BaseModel, use_created_at=False, use_updated_at=False):
    pass

# Case 3: カスタム __init_subclass__
class CustomBase(BaseModel):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # カスタムロジック
```

### 5. パフォーマンスへの影響

**疑問**:
- 毎回 `__annotations__` を新規作成することでオーバーヘッドはないか？
- モデル定義時（クラス作成時）のみなので問題ないか？

**調査方法**:
```python
import timeit

# Before (hasattr)
def test_hasattr():
    class Model(BaseModel):
        pass

# After (cls.__dict__)
def test_dict_check():
    class Model(BaseModel):
        pass

# ベンチマーク
print(timeit.timeit(test_hasattr, number=10000))
print(timeit.timeit(test_dict_check, number=10000))
```

### 6. 代替実装の検討

**Option B**: stub ファイル (`.pyi`) を使用
```python
# repom/base_model.pyi
from sqlalchemy.orm import Mapped
from datetime import datetime

class BaseModel:
    id: Mapped[int]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**Pros**:
- 型チェックが静的に解決される
- 実行時のオーバーヘッドがない

**Cons**:
- stub ファイルの管理が煩雑
- `use_id=False` などの動的な挙動を表現できない

**Option C**: `typing.TYPE_CHECKING` を活用
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from datetime import datetime
    id: Mapped[int]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**Pros**:
- 型チェック時のみ評価される
- 実行時のオーバーヘッドがない

**Cons**:
- 動的カラム追加との整合性が取れない

## 検証手順

1. **Python の `__annotations__` 動作確認**
   - テストコードを作成して継承動作を確認
   - 標準的なパターンを調査

2. **SQLAlchemy 2.0 ドキュメント精読**
   - 推奨パターンを確認
   - 動的カラム追加の是非を確認

3. **既存テストの網羅性確認**
   - 現在のテストで十分か？
   - エッジケースのテストを追加

4. **FastAPI 統合テスト作成**
   - 実際の使用シナリオでテスト
   - response_model との整合性確認

5. **consuming project での検証**
   - 実プロジェクトで動作確認
   - 既存コードへの影響を確認

## 期待される成果物

### 1. 調査レポート
- `docs/research/annotation_inheritance_analysis.md`
- Python の `__annotations__` 継承動作の解説
- SQLAlchemy 2.0 との整合性確認
- ベストプラクティスの提案

### 2. テストケースの追加
- `tests/unit_tests/test_annotation_inheritance.py`
- 多重継承のテスト
- Mixin との組み合わせテスト
- エッジケースの網羅

### 3. ドキュメント更新
- `docs/technical/base_model_implementation.md` (新規作成)
- `__init_subclass__` の実装詳細
- `__annotations__` の扱い方
- トラブルシューティング

### 4. Issue #006 への反映
- 調査結果を Phase 1 の評価に反映
- 必要に応じて実装を修正
- ベストプラクティスを文書化

## 完了条件

- [ ] Python の `__annotations__` 継承動作を理解
- [ ] SQLAlchemy 2.0 の推奨パターンとの整合性を確認
- [ ] 現在の実装が適切であることを検証（または改善提案）
- [ ] エッジケースのテストを追加
- [ ] FastAPI 統合テストを作成
- [ ] 調査レポートを作成（`docs/research/annotation_inheritance_analysis.md`）
- [ ] ドキュメントを更新（`docs/technical/base_model_implementation.md`）
- [ ] Issue #006 に結果を反映

## リスク評価

### リスク 1: 現在の実装が不適切

**影響**: Issue #006 を再実装する必要がある

**確率**: 低（テストは通っている）

**軽減策**: 早期に調査を実施

### リスク 2: consuming project への影響

**影響**: 既存プロジェクトが壊れる可能性

**確率**: 中（動的カラム追加は特殊なパターン）

**軽減策**: 実プロジェクトでの検証を実施

### リスク 3: パフォーマンス劣化

**影響**: モデル定義が遅くなる

**確率**: 低（クラス作成時のみ）

**軽減策**: ベンチマークテストで確認

## 関連ドキュメント

- **Issue #006**: SQLAlchemy 2.0 スタイルへの移行
- **BaseModel**: `repom/base_model.py`
- **BaseModelAuto**: `repom/base_model_auto.py`
- **テスト**: `tests/unit_tests/test_base_model_auto.py`

## 参考資料

### Python 公式ドキュメント
- [PEP 526 - Syntax for Variable Annotations](https://www.python.org/dev/peps/pep-0526/)
- [Data model - `__annotations__`](https://docs.python.org/3/reference/datamodel.html#object.__annotations__)

### SQLAlchemy 2.0
- [Declarative Mapping](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html)
- [Mapped and mapped_column()](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#using-annotated-declarative-table)

### Stack Overflow / GitHub
- 類似問題の検索キーワード: "python annotations inheritance", "sqlalchemy dynamic columns", "dataclass __annotations__"

---

**作成者**: AI Assistant  
**作成日**: 2025-11-15  
**優先度**: 中（Phase 1 完了後に調査）  
**関連 Issue**: #006
