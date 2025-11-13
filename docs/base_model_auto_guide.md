# repom: BaseModelAuto と response_field 機能ガイド

## 概要

repom パッケージでは、SQLAlchemy モデルから FastAPI の Pydantic スキーマを自動生成する機能を提供しています。

1. **BaseModelAuto**: Column の `info` メタデータから Create/Update スキーマを自動生成
2. **response_field デコレータ**: `to_dict()` メソッドの追加フィールドを宣言し、Response スキーマを自動生成

この機能により、手動でのスキーマ定義を大幅に削減し、DRY 原則に従った開発が可能になります。

## BaseModelAuto: 自動スキーマ生成

### 基本的な使い方

```python
from repom.base_model_auto import BaseModelAuto
from sqlalchemy import Column, String, Integer, Boolean

class TimeActivityModel(BaseModelAuto):
    __tablename__ = "time_activities"
    
    use_id = True  # id カラムを使用
    use_created_at = True
    use_updated_at = True

    name = Column(
        String(100), 
        nullable=False, 
        unique=True,
        info={'description': '活動名（重複不可）'}
    )
    color = Column(
        String(7), 
        nullable=False,
        info={'description': 'カラーコード（例: #FF5733）'}
    )
    sort_order = Column(
        Integer, 
        nullable=False, 
        default=0,
        info={'description': '表示順序'}
    )
    is_active = Column(
        Boolean, 
        nullable=False, 
        default=True,
        info={'description': '有効/無効フラグ'}
    )
```

### スキーマ自動生成

```python
# Create スキーマを自動生成
TimeActivityCreate = TimeActivityModel.get_create_schema()

# Update スキーマを自動生成
TimeActivityUpdate = TimeActivityModel.get_update_schema()

# FastAPI で使用
from fastapi import FastAPI
app = FastAPI()

@app.post("/activities/", response_model=TimeActivityResponse)
def create_activity(activity: TimeActivityCreate):
    # ...
```

### 生成されるスキーマの内容

**Create スキーマ** (`TimeActivityCreate`):
```python
# 自動生成される内容（概念的表現）
class TimeActivityCreate(BaseModel):
    name: str = Field(description='活動名（重複不可）', max_length=100)
    color: str = Field(description='カラーコード（例: #FF5733）', max_length=7)
    sort_order: int = Field(default=0, description='表示順序')
    is_active: bool = Field(default=True, description='有効/無効フラグ')
    # id, created_at, updated_at は除外される
```

**Update スキーマ** (`TimeActivityUpdate`):
```python
# 自動生成される内容（概念的表現）
class TimeActivityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description='活動名（重複不可）', max_length=100)
    color: Optional[str] = Field(default=None, description='カラーコード（例: #FF5733）', max_length=7)
    sort_order: Optional[int] = Field(default=None, description='表示順序')
    is_active: Optional[bool] = Field(default=None, description='有効/無効フラグ')
    # すべてのフィールドが Optional になる
```

### Column.info メタデータのオプション

| キー | 型 | 説明 |
|------|----|----|
| `description` | str | フィールドの説明（Field の description に使用） |
| `in_create` | bool | Create スキーマに含めるか（デフォルト: auto） |
| `in_update` | bool | Update スキーマに含めるか（デフォルト: auto） |

### 自動除外ルール

以下のフィールドは自動的に除外されます：

1. **システムカラム**: `id`, `created_at`, `updated_at`
2. **外部キー**: ForeignKey を持つカラム（`*_id`）
3. **明示的除外**: `info={'in_create': False}` または `info={'in_update': False}`

### カスタム除外

```python
# 特定のフィールドを除外
UserCreateCustom = UserModel.get_create_schema(
    exclude_fields=['password_hash', 'internal_notes']
)
```

### コード削減効果

**従来の手動定義**:
```python
# 手動で定義する場合（77行）
class TimeActivityCreate(BaseModel):
    name: str = Field(description='活動名（重複不可）', max_length=100)
    color: str = Field(description='カラーコード（例: #FF5733）', max_length=7)
    # ... 続く

class TimeActivityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description='活動名（重複不可）', max_length=100)
    color: Optional[str] = Field(default=None, description='カラーコード（例: #FF5733）', max_length=7)
    # ... 続く
```

**BaseModelAuto 使用**:
```python
# 自動生成（18行）
TimeActivityCreate = TimeActivityModel.get_create_schema()
TimeActivityUpdate = TimeActivityModel.get_update_schema()
```

**削減効果**: 77% のコード削減（77行 → 18行）

## response_field デコレータ: Response スキーマ自動生成

### 基本的な使い方

```python
from repom.base_model import BaseModel

class VoiceScriptLineModel(BaseModel):
    # ... カラム定義
    
    @property
    def text(self) -> str | None:
        """最新の Log のテキストを返す"""
        log = self.latest_log
        return log.text if log else None
    
    @property
    def has_voice(self) -> bool:
        """音声が生成済みかどうか"""
        return self.asset_item_id is not None

    @BaseModel.response_field(
        text=str | None,
        has_voice=bool,
        latest_job=dict | None,
        logs="List[VoiceScriptLineLogResponse]"  # 前方参照
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            "text": self.text,
            "has_voice": self.has_voice,
            "latest_job": self.latest_job,
            "logs": [log.to_dict() for log in self.logs],
        })
        return data
```

### Response スキーマ生成

```python
# Response スキーマを自動生成
VoiceScriptLineResponse = VoiceScriptLineModel.get_response_schema()

# 前方参照を解決
VoiceScriptLineResponse = VoiceScriptLineModel.get_response_schema(
    forward_refs={
        'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse
    }
)
```

### 生成されるスキーマの内容

```python
# 自動生成される内容（概念的表現）
class VoiceScriptLineResponse(BaseModel):
    # SQLAlchemy カラムから自動取得
    id: int
    scene_id: int
    notes: str
    character_name: str
    lang: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # @response_field で宣言された追加フィールド
    text: str | None
    has_voice: bool
    latest_job: dict | None
    logs: List[VoiceScriptLineLogResponse]
```

### 前方参照の解決

**問題**: 循環参照やまだ定義されていないクラスへの参照

**解決法**: 文字列型アノテーションと forward_refs

```python
# 文字列で型を指定（前方参照）
@BaseModel.response_field(
    related_items="List[RelatedItemResponse]",
    parent_item="ParentItemResponse | None"
)
def to_dict(self):
    # ...

# スキーマ生成時に前方参照を解決
ResponseSchema = MyModel.get_response_schema(
    forward_refs={
        'RelatedItemResponse': RelatedItemResponse,
        'ParentItemResponse': ParentItemResponse
    }
)
```

### パフォーマンス最適化

1. **スキーマキャッシュ**: 生成されたスキーマは自動的にキャッシュされる
2. **メタデータのみ**: デコレータは型情報を保存するだけ（実行時影響なし）
3. **遅延評価**: スキーマは必要になった時点で生成される

```python
# 初回はスキーマ生成
schema1 = MyModel.get_response_schema()  # 生成処理

# 2回目以降はキャッシュから取得
schema2 = MyModel.get_response_schema()  # キャッシュ取得（高速）
```

## 複合主キー対応

### use_composite_pk フラグの導入

**問題**: BaseModelAuto が BaseModel を継承するため、デフォルトで `use_id=False` を設定していても、複合主キーの意図が不明瞭だった

**解決策**: `use_composite_pk=True` フラグを導入し、複合主キーの意図を明確化

```python
class BaseModel(Base):
    __abstract__ = True
    
    use_id = True  # デフォルトで id を使用
    use_created_at = False
    use_updated_at = False
    use_composite_pk = False  # 複合主キーフラグ（NEW!）
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # 複合主キーの場合は id カラムを追加しない（最優先）
        if cls.use_composite_pk:
            # 既に id カラムが追加されている場合は削除
            if hasattr(cls, 'id') and isinstance(getattr(cls, 'id', None), Column):
                delattr(cls, 'id')
        elif cls.use_id:
            # 通常の id カラムを追加
            cls.id = Column(Integer, primary_key=True)
```

### 使用例

**複合主キーのモデル**:
```python
class TimeBlockModel(BaseModelAuto):
    __tablename__ = "time_blocks"
    
    # 複合主キーを明示的に宣言
    use_composite_pk = True  # id カラムを使用しない（最優先）
    use_created_at = True
    use_updated_at = True
    
    date = Column(Date, primary_key=True, info={'description': '日付'})
    start_time = Column(Time, primary_key=True, info={'description': '開始時刻'})
    activity_id = Column(Integer, ForeignKey('time_activities.id'))
```

**通常の主キーのモデル**:
```python
class TimeActivityModel(BaseModelAuto):
    __tablename__ = "time_activities"
    
    # 通常の id カラムを使用
    use_id = True
    use_created_at = True
    use_updated_at = True
    
    name = Column(String(100), nullable=False, info={'description': '活動名'})
```

**use_id=False のモデル（カスタム主キー）**:
```python
class ProductModel(BaseModelAuto):
    __tablename__ = "products"
    
    # id を使わず、独自のカラムを主キーにする
    use_id = False
    
    code = Column(String(50), primary_key=True, info={'description': '商品コード'})
    name = Column(String(100), nullable=False, info={'description': '商品名'})
```

### フラグの優先順位

1. **use_composite_pk=True**: 最優先。id カラムを追加しない（複合主キー用）
2. **use_id=True**: use_composite_pk が False の場合に有効。id カラムを追加
3. **use_id=False**: id カラムを追加しない（単一カスタム主キー用）

### メリット

- **意図が明確**: `use_composite_pk=True` で複合主キーであることが一目瞭然
- **エラー防止**: 誤って id カラムが追加されることがない
- **後方互換性**: 既存の `use_id=True/False` はそのまま使用可能

## 実際の使用例

### 完全な例: TimeActivity

**モデル定義**:
```python
class TimeActivityModel(BaseModelAuto):
    __tablename__ = "time_activities"
    use_id = True
    use_created_at = True
    use_updated_at = True

    name = Column(String(100), nullable=False, unique=True, 
                  info={'description': '活動名（重複不可）'})
    color = Column(String(7), nullable=False, 
                   info={'description': 'カラーコード（例: #FF5733）'})
    sort_order = Column(Integer, nullable=False, default=0, 
                        info={'description': '表示順序'})
    is_active = Column(Boolean, nullable=False, default=True, 
                       info={'description': '有効/無効フラグ'})
```

**スキーマ生成**:
```python
# 自動生成（1行ずつ）
TimeActivityResponse = TimeActivityModel.get_response_schema()
TimeActivityCreate = TimeActivityModel.get_create_schema()
TimeActivityUpdate = TimeActivityModel.get_update_schema()
```

**FastAPI 使用例**:
```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

app = FastAPI()

@app.get("/activities/", response_model=List[TimeActivityResponse])
def list_activities(db: Session = Depends(get_db)):
    activities = db.query(TimeActivityModel).all()
    return [activity.to_dict() for activity in activities]

@app.post("/activities/", response_model=TimeActivityResponse)
def create_activity(
    activity: TimeActivityCreate, 
    db: Session = Depends(get_db)
):
    db_activity = TimeActivityModel(**activity.dict())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity.to_dict()

@app.patch("/activities/{activity_id}", response_model=TimeActivityResponse)
def update_activity(
    activity_id: int,
    updates: TimeActivityUpdate,
    db: Session = Depends(get_db)
):
    activity = db.query(TimeActivityModel).get(activity_id)
    activity.update_from_dict(updates.dict(exclude_unset=True))
    db.commit()
    db.refresh(activity)
    return activity.to_dict()
```

## ベストプラクティス

### 1. Column.info の活用

```python
# Good: 詳細な説明とバリデーション情報
name = Column(
    String(100), 
    nullable=False, 
    unique=True,
    info={
        'description': '活動名（重複不可、最大100文字）',
        'in_create': True,
        'in_update': True
    }
)

# Bad: info なし
name = Column(String(100), nullable=False, unique=True)
```

### 2. 適切な型アノテーション

```python
# Good: 具体的な型指定
@BaseModel.response_field(
    total_count=int,
    items="List[ItemResponse]",
    metadata="Dict[str, Any]"
)

# Bad: すべて Any
@BaseModel.response_field(
    total_count=Any,
    items=Any,
    metadata=Any
)
```

### 3. 前方参照の管理

```python
# Good: 依存関係を明確に管理
def create_schemas():
    # 基本スキーマを先に作成
    BaseResponse = BaseModel.get_response_schema()
    
    # 依存スキーマを後で作成
    ComplexResponse = ComplexModel.get_response_schema(
        forward_refs={'BaseResponse': BaseResponse}
    )
    
    return BaseResponse, ComplexResponse
```

### 4. パフォーマンス考慮

```python
# Good: アプリケーション起動時にスキーマを生成
def initialize_schemas():
    schemas = {}
    schemas['user'] = UserModel.get_response_schema()
    schemas['post'] = PostModel.get_response_schema()
    return schemas

# アプリケーション起動時
app_schemas = initialize_schemas()
```

## トラブルシューティング

### 1. 前方参照エラー

**エラー**: `NameError: name 'SomeResponse' is not defined`

**解決法**:
```python
# 文字列で型を指定
@BaseModel.response_field(
    related="List[SomeResponse]"  # 文字列で指定
)

# スキーマ生成時に解決
schema = MyModel.get_response_schema(
    forward_refs={'SomeResponse': SomeResponse}
)
```

### 2. 複合主キーでの AttributeError

**エラー**: `AttributeError: type object 'MyModel' has no attribute 'id'`

**解決法**:
```python
class MyRepository(BaseRepository[MyModel]):
    def set_find_option(self, query, **kwargs):
        # id.asc() の代わりに複合キーを使用
        order_by = kwargs.get('order_by', [
            self.model.date.asc(), 
            self.model.time.asc()
        ])
        # ... 実装
```

### 3. スキーマキャッシュの問題

**問題**: 開発中にスキーマが更新されない

**解決法**:
```python
# キャッシュをクリア
MyModel._response_schemas.clear()
MyModel._create_schemas.clear()
MyModel._update_schemas.clear()

# または Python プロセスを再起動
```

## 今後の改善予定

1. ~~**複合主キー専用フラグ**: `use_composite_pk=True` の追加~~ ✅ **完了**
2. **バリデーター Mixin**: カスタムバリデーション処理の統合
3. **OpenAPI 統合**: Swagger UI での自動ドキュメント生成強化
4. **型推論改善**: より正確な Python 型の自動検出

---

**関連ファイル**:
- `repom/base_model.py`
- `repom/base_model_auto.py`
- `tests/unit_tests/test_base_model_auto.py`
- `tests/unit_tests/test_response_field.py`

**作成日**: 2025-11-13  
**更新日**: 2025-11-13  
**最終更新**: use_composite_pk フラグ実装完了
