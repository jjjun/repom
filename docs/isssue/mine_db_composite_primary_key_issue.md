# mine_db: BaseModelAuto 複合主キー対応の問題調査

## 概要

mine_db の BaseModelAuto クラスにおいて、複合主キー（`use_id=False`）を使用する際の設計上の問題と改善提案をまとめる。

## 発見された問題

### 1. 継承による意図しない id カラムの追加

**問題の詳細:**
- `BaseModelAuto` が `BaseModel` を継承している
- `BaseModel.use_id = True` がデフォルト値として設定されている
- `BaseModelAuto` で `use_id` を明示的に設定していないため、親クラスの `use_id=True` を継承
- `BaseModel.__init_subclass__` により、`BaseModelAuto` クラス自体に `id` カラムが追加される
- サブクラスで `use_id=False` を設定しても、既に追加された `id` カラムは削除されない

**再現コード:**
```python
# 問題のあるコード
class BaseModelAuto(BaseModel):
    __abstract__ = True
    # use_id が明示されていない → BaseModel.use_id=True を継承

class TimeBlockModel(BaseModelAuto):
    use_id = False  # ← これを設定しても id は削除されない
    date = Column(Date, primary_key=True)
    start_time = Column(Time, primary_key=True)
```

**結果:**
```python
# 期待: primary_key = [date, start_time]
# 実際: primary_key = [date, start_time, id]  # id が予期せず含まれる
```

### 2. Python クラス属性継承の仕様

**技術的背景:**
- Python のクラス属性は継承される
- `BaseModelAuto` クラス定義時点で `BaseModel.__init_subclass__` が実行される
- この時点で `BaseModelAuto.use_id = True`（継承）のため、`BaseModelAuto` に `id` カラムが追加される
- サブクラスは `BaseModelAuto` を継承するため、追加済みの `id` カラムも継承する

**検証コマンド:**
```python
from src.models.time_block import TimeBlockModel
print("use_id:", TimeBlockModel.use_id)
print("\nColumns:")
[print(f"  {col.name}: primary_key={col.primary_key}") for col in TimeBlockModel.__table__.columns]
print("\nPrimary keys:")
print([col.name for col in TimeBlockModel.__table__.primary_key.columns])
```

### 3. BaseRepository の互換性問題

**問題:**
- `BaseRepository.set_find_option()` が `self.model.id.asc()` の存在を前提としている
- 複合主キーモデルには `id` が存在しないため `AttributeError` が発生

**エラー例:**
```python
AttributeError: type object 'TimeBlockModel' has no attribute 'id'
```

## 暫定的な解決策（実装済み）

### 1. BaseModelAuto のデフォルト値設定
```python
class BaseModelAuto(BaseModel):
    __abstract__ = True
    # 明示的にデフォルト値を設定
    use_id = False
    use_created_at = False
    use_updated_at = False
```

### 2. 既存モデルでの明示的設定
```python
class FinRecurringPaymentModel(BaseModelAuto):
    use_id = True  # 明示的に設定

class TimeActivityModel(BaseModelAuto):
    use_id = True  # 明示的に設定
```

### 3. BaseRepository の拡張
```python
class TimeBlockRepository(BaseRepository[TimeBlockModel]):
    def set_find_option(self, query, **kwargs):
        # id.asc() の代わりに複合キーでのソート
        order_by = kwargs.get('order_by', [self.model.date.asc(), self.model.start_time.asc()])
        # ... 実装
```

## 根本的な改善提案

### 案1: BaseModelAuto に専用フラグ追加（推奨）

**概要:**
複合主キー用の専用フラグを追加し、意図を明確にする。

```python
class BaseModelAuto(BaseModel):
    __abstract__ = True
    use_composite_pk = False  # 新フラグ
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # 複合主キーの場合は id を削除
        if cls.use_composite_pk and hasattr(cls, 'id'):
            if isinstance(getattr(cls, 'id', None), Column):
                delattr(cls, 'id')

# 使用例
class TimeBlockModel(BaseModelAuto):
    use_composite_pk = True  # 意図が明確
    use_created_at = True
    use_updated_at = True
```

**メリット:**
- 後方互換性100%（既存コード修正不要）
- 意図が明確（`use_composite_pk=True`）
- 複合主キーは少数派なので特別フラグが適切

### 案2: クラス属性の優先順位明確化

```python
class BaseModel(Base):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # サブクラスで明示的に設定されているかチェック
        if 'use_id' in cls.__dict__:
            should_use_id = cls.__dict__['use_id']
        else:
            should_use_id = cls.use_id
            
        if should_use_id:
            cls.id = Column(Integer, primary_key=True)
```

### 案3: 明示的な基底クラス分離

```python
class BaseModelAuto(BaseModel):
    """通常のモデル用（id を持つ）"""
    __abstract__ = True

class BaseModelAutoComposite(BaseModel):
    """複合主キー用（id を持たない）"""
    __abstract__ = True
    use_id = False
    use_created_at = False
    use_updated_at = False
```

### 案4: デコレータパターン

```python
@composite_primary_key
class TimeBlockModel(BaseModelAuto):
    date = Column(Date, primary_key=True)
    start_time = Column(Time, primary_key=True)
```

## 現在の影響範囲

### 修正済みファイル
- `submod/mine_db/mine_db/base_model_auto.py`: デフォルト値設定
- `src/models/fin_recurring_payment.py`: `use_id = True` 明示
- `src/models/time_activity.py`: `use_id = True` 明示
- `src/repositories/time_block.py`: `set_find_option` オーバーライド

### テスト結果
- 31/34 テスト成功（91%）
- 残り3件は統計クエリの NULL 処理問題（別件）

## 推奨される対応

1. **短期**: 案1（専用フラグ）の実装
2. **中期**: BaseRepository の複合主キー対応強化
3. **長期**: 複合主キー専用の Repository 基底クラス検討

## 参考情報

### 関連するファイル
- `submod/mine_db/mine_db/base_model.py`
- `submod/mine_db/mine_db/base_model_auto.py`
- `submod/mine_db/mine_db/base_repository.py`

### 検証コマンド
```bash
# 複合主キーの動作確認
poetry run python -c "
from src.models.time_block import TimeBlockModel
print('Columns:', [col.name for col in TimeBlockModel.__table__.columns])
print('Primary keys:', [col.name for col in TimeBlockModel.__table__.primary_key.columns])
"

# テスト実行
poetry run pytest tests/unit_tests/test_time_block.py -v
```

### 関連コミット
- `d01241c`: Fix BaseModelAuto use_id inheritance issue

---

**作成日**: 2025-11-12  
**担当**: GitHub Copilot  
**mine_db リポジトリでの対応**: 案1（専用フラグ）の実装を推奨
