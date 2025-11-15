# BaseModelAuto 完全ガイド

**このドキュメントについて**: repom パッケージの BaseModelAuto によるスキーマ自動生成機能の完全ガイドです。SQLAlchemy モデルから Pydantic スキーマを自動生成し、FastAPI での開発を効率化します。

## 📚 目次

1. [概要](#概要)
2. [BaseModelAuto: Create/Update スキーマ自動生成](#basemodelauto-createupdate-スキーマ自動生成)
3. [Response スキーマ & @response_field デコレータ](#response-スキーマ--responsefield-デコレータ)
4. [前方参照の解決](#前方参照の解決)
5. [スキーマ生成ルール詳細](#スキーマ生成ルール詳細)
6. [複合主キー対応](#複合主キー対応)
7. [技術詳細: 内部実装](#技術詳細-内部実装)
8. [FastAPI 統合例](#fastapi-統合例)
9. [ベストプラクティス](#ベストプラクティス)
10. [トラブルシューティング](#トラブルシューティング)

---

## 概要

repom パッケージでは、SQLAlchemy モデルから FastAPI の Pydantic スキーマを自動生成する機能を提供しています。

### このガイドで学べること

- ✅ SQLAlchemy モデルから Pydantic スキーマを自動生成
- ✅ Create/Update/Response スキーマの生成方法
- ✅ @response_field デコレータの使い方
- ✅ 前方参照の解決方法
- ✅ FastAPI での実装パターン
- ✅ トラブルシューティングと解決方法

### 主な機能

1. **BaseModelAuto**: Column の `info` メタデータから Create/Update スキーマを自動生成
2. **@response_field デコレータ**: `to_dict()` メソッドの追加フィールドを宣言し、Response スキーマを自動生成

### コード削減効果

**従来の手動定義**:
```python
# 手動で定義する場合（77行）
class TimeActivityCreate(BaseModel):
    name: str = Field(description='活動名（重複不可）', max_length=100)
    color: str = Field(description='カラーコード（例: #FF5733）', max_length=7)
    sort_order: int = Field(default=0, description='表示順序')
    is_active: bool = Field(default=True, description='有効/無効フラグ')

class TimeActivityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description='活動名（重複不可）', max_length=100)
    color: Optional[str] = Field(default=None, description='カラーコード（例: #FF5733）', max_length=7)
    sort_order: Optional[int] = Field(default=None, description='表示順序')
    is_active: Optional[bool] = Field(default=None, description='有効/無効フラグ')
```

**BaseModelAuto 使用**:
```python
# 自動生成（2行）
TimeActivityCreate = TimeActivityModel.get_create_schema()
TimeActivityUpdate = TimeActivityModel.get_update_schema()
```

**削減効果**: 77% のコード削減（77行 → 18行）

---

## BaseModelAuto: Create/Update スキーマ自動生成

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
| `in_response` | bool | Response スキーマに含めるか（デフォルト: True） |

### 自動除外ルール

以下のフィールドは自動的に除外されます：

1. **システムカラム（Create/Update のみ）**: `id`, `created_at`, `updated_at`
   - Response スキーマには含まれます
2. **外部キー**: ForeignKey を持つカラム（`*_id`）
3. **明示的除外**: `info={'in_create': False}` または `info={'in_update': False}`

### カスタム除外

```python
# 特定のフィールドを除外
UserCreateCustom = UserModel.get_create_schema(
    exclude_fields=['password_hash', 'internal_notes']
)
```

---

## Response スキーマ & @response_field デコレータ

### 基本的な使い方

```python
from repom.base_model import BaseModel

class VoiceScriptLineModel(BaseModel):
    __tablename__ = "voice_script_lines"
    
    # ... カラム定義
    scene_id = Column(Integer, ForeignKey('scenes.id'))
    notes = Column(String(500))
    character_name = Column(String(100))
    
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
VoiceScriptLineLogResponse = VoiceScriptLineLogModel.get_response_schema()
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
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # @response_field で宣言された追加フィールド
    text: str | None
    has_voice: bool
    latest_job: dict | None
    logs: List[VoiceScriptLineLogResponse]
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

---

## 前方参照の解決

### 問題: 循環参照やまだ定義されていないクラスへの参照

```python
# ❌ これはエラーになる
class ReviewModel(BaseModel):
    @BaseModel.response_field(
        related_books=List[BookResponse]  # BookResponse がまだ定義されていない
    )
    def to_dict(self):
        ...
```

### 解決法: 文字列型アノテーションと forward_refs

```python
# ✅ 文字列で型を指定（前方参照）
class ReviewModel(BaseModel):
    @BaseModel.response_field(
        related_books="List[BookResponse]",  # 文字列で指定
        parent_item="ParentItemResponse | None"
    )
    def to_dict(self):
        return {
            "related_books": [book.to_dict() for book in self.books],
            "parent_item": self.parent.to_dict() if self.parent else None
        }

# スキーマ生成時に前方参照を解決
BookResponse = BookModel.get_response_schema()
ParentItemResponse = ParentItemModel.get_response_schema()

ResponseSchema = ReviewModel.get_response_schema(
    forward_refs={
        'BookResponse': BookResponse,
        'ParentItemResponse': ParentItemResponse
    }
)
```

### Phase 1 改善（2025-11-14）

**標準型（`List`, `Dict`, `Optional` など）は自動的に解決されるため、`forward_refs` に含める必要はありません。カスタムモデルの前方参照のみ指定してください。**

```python
# ✅ 正しい使い方
@BaseModel.response_field(
    tags=List[str],           # 標準型：forward_refs 不要
    metadata=Optional[dict],  # 標準型：forward_refs 不要
    related_books="List[BookResponse]"  # カスタム型：forward_refs 必要
)
def to_dict(self):
    ...

# スキーマ生成（カスタム型だけ指定）
BookResponse = BookModel.get_response_schema()
ResponseSchema = MyModel.get_response_schema(
    forward_refs={'BookResponse': BookResponse}  # カスタム型のみ
    # 'List' は自動的に解決されるため不要
)
```

### エラーハンドリング（Phase 2 改善）

スキーマ生成時に前方参照が解決できない場合、環境に応じて異なる動作をします。

#### 開発環境（`EXEC_ENV=dev`）

**動作**: 例外を発生させて処理を停止

```python
from repom.base_model import SchemaGenerationError

try:
    TaskResponse = Task.get_response_schema(
        forward_refs={'MissingType': MissingType}  # 未定義型
    )
except SchemaGenerationError as e:
    print(e)
    # 出力例:
    # Failed to generate Pydantic schema for 'TaskResponse'.
    # Error: name 'MissingType' is not defined
    #
    # Undefined types detected: MissingType
    #
    # Solution:
    #   Add missing types to forward_refs parameter:
    #   schema = Task.get_response_schema(
    #       forward_refs={
    #           'MissingType': MissingType,
    #       }
    #   )
```

#### 本番環境（`EXEC_ENV=prod` または未設定）

**動作**: ログにエラーを記録し、警告を表示して処理を続行

```python
# 本番環境では例外を投げずに警告のみ
TaskResponse = Task.get_response_schema(
    forward_refs={'MissingType': MissingType}
)
# 警告: Failed to rebuild TaskResponse. See logs for details.
```

---

## スキーマ生成ルール詳細

### デフォルトの包含/除外ルール

| フィールド種類 | Create | Update | Response | 理由 |
|---------------|--------|--------|----------|------|
| `id` | ❌ | ❌ | ✅ | システムが自動生成 |
| `created_at` | ❌ | ❌ | ✅ | システムが自動設定 |
| `updated_at` | ❌ | ❌ | ✅ | システムが自動更新 |
| 外部キー (`*_id`) | ✅ | ✅ | ✅ | 関連を指定するため必要 |
| 通常カラム | ✅ | ✅ | ✅ | ユーザーデータ |
| `@property` | ❌ | ❌ | ❌ | データベースに存在しない |
| `@response_field` | ❌ | ❌ | ✅ | Response 専用の追加フィールド |

### Column.info による制御

```python
class UserModel(BaseModelAuto):
    __tablename__ = "users"
    
    # Create にのみ含める（パスワード設定）
    password = Column(
        String(255),
        info={
            'in_create': True,
            'in_update': False,  # パスワード変更は別エンドポイント
            'in_response': False  # レスポンスには含めない
        }
    )
    
    # Update にのみ含める
    profile_image_url = Column(
        String(500),
        info={
            'in_create': False,  # 初回は空でOK
            'in_update': True,   # 後で更新可能
            'in_response': True
        }
    )
    
    # Response にのみ含める（計算フィールド）
    @BaseModel.response_field(
        full_name=str,
        is_premium=bool
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'full_name': f"{self.first_name} {self.last_name}",
            'is_premium': self.subscription_tier == 'premium'
        })
        return data
```

---

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

---

## 技術詳細: 内部実装

### アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│                    BaseModel                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  @response_field decorator                                  │
│    └─> Stores type metadata in method._response_fields      │
│                                                              │
│  get_response_schema()                                       │
│    ├─> Reads SQLAlchemy column definitions                  │
│    ├─> Reads @response_field metadata                       │
│    ├─> Registers fields in _EXTRA_FIELDS_REGISTRY           │
│    ├─> Generates Pydantic schema via create_model()         │
│    ├─> Calls model_rebuild() if forward_refs provided       │
│    └─> Caches schema in _response_schemas                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Global Storage:
  _EXTRA_FIELDS_REGISTRY: WeakKeyDictionary[type, Dict[str, Any]]
  BaseModel._response_schemas: Dict[str, Type[Any]]
```

### データフロー

```
1. Model Definition
   ┌──────────────────────────────┐
   │ class MyModel(BaseModel):    │
   │   name = Column(String)      │
   │                              │
   │   @response_field(           │
   │     tags=List[str]           │
   │   )                          │
   │   def to_dict(self):         │
   │     ...                      │
   └──────────────────────────────┘
                ↓
2. Decorator Execution (at import time)
   ┌──────────────────────────────┐
   │ to_dict._response_fields =   │
   │   {'tags': List[str]}        │
   └──────────────────────────────┘
                ↓
3. Schema Generation (at runtime)
   ┌──────────────────────────────┐
   │ schema = MyModel.            │
   │   get_response_schema()      │
   └──────────────────────────────┘
                ↓
4. Registration (lazy, on first call)
   ┌──────────────────────────────┐
   │ _EXTRA_FIELDS_REGISTRY[cls]  │
   │   = {'tags': List[str]}      │
   └──────────────────────────────┘
                ↓
5. Pydantic Schema Creation
   ┌──────────────────────────────┐
   │ create_model(                │
   │   'MyModelResponse',         │
   │   name=(str, ...),           │
   │   tags=(List[str], ...)      │
   │ )                            │
   └──────────────────────────────┘
                ↓
6. Caching
   ┌──────────────────────────────┐
   │ _response_schemas[           │
   │   'MyModel::MyModelResponse' │
   │ ] = schema                   │
   └──────────────────────────────┘
```

### キャッシュキーの形式

```python
cache_key = f"{cls.__name__}::{schema_name}"
if forward_refs:
    cache_key += f"::{','.join(sorted(forward_refs.keys()))}"
```

**例**:
- `"MyModel::MyModelResponse"`
- `"MyModel::MyModelResponse::ChildResponse,ParentResponse"`

### _EXTRA_FIELDS_REGISTRY

**型**: `WeakKeyDictionary[type, Dict[str, Any]]`

**目的**: モデルクラスを追加フィールドにマッピングするグローバルレジストリ

**WeakKeyDictionary を使う理由**:
- モデルクラスのガベージコレクションを許可
- 長時間実行されるアプリケーションでのメモリリークを防ぐ
- 参照されなくなったモデルクラスを自動的にクリーンアップ

---

## FastAPI 統合例

### 基本的なCRUD エンドポイント

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

app = FastAPI()

# モジュールレベルでスキーマを生成（推奨）
TimeActivityResponse = TimeActivityModel.get_response_schema()
TimeActivityCreate = TimeActivityModel.get_create_schema()
TimeActivityUpdate = TimeActivityModel.get_update_schema()

@app.get("/activities/", response_model=List[TimeActivityResponse])
def list_activities(db: Session = Depends(get_db)):
    """活動一覧を取得"""
    activities = db.query(TimeActivityModel).all()
    return [activity.to_dict() for activity in activities]

@app.get("/activities/{activity_id}", response_model=TimeActivityResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    """特定の活動を取得"""
    activity = db.query(TimeActivityModel).get(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity.to_dict()

@app.post("/activities/", response_model=TimeActivityResponse, status_code=201)
def create_activity(
    activity: TimeActivityCreate, 
    db: Session = Depends(get_db)
):
    """新しい活動を作成"""
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
    """活動を更新"""
    activity = db.query(TimeActivityModel).get(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # exclude_unset=True で送信されたフィールドのみ更新
    activity.update_from_dict(updates.dict(exclude_unset=True))
    db.commit()
    db.refresh(activity)
    return activity.to_dict()

@app.delete("/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    """活動を削除"""
    activity = db.query(TimeActivityModel).get(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    db.delete(activity)
    db.commit()
```

### GenericListResponse パターン

リストエンドポイントでページネーション情報を含める場合：

```python
from pydantic import BaseModel as PydanticBaseModel
from typing import Generic, TypeVar, List

T = TypeVar('T')

class GenericListResponse(PydanticBaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 10

# FastAPI で使用
TaskResponse = Task.get_response_schema()

@router.get("/tasks", response_model=GenericListResponse[TaskResponse])
def get_tasks(page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    offset = (page - 1) * page_size
    tasks = db.query(Task).offset(offset).limit(page_size).all()
    total = db.query(Task).count()
    
    return {
        'items': [task.to_dict() for task in tasks],
        'total': total,
        'page': page,
        'page_size': page_size
    }
```

### タイミングに関する考慮事項

#### 1. インポート時のスキーマ生成（推奨）

```python
# api/endpoints/items.py
from src.models.my_model import MyModel

# ✅ モジュールインポート時に一度だけ生成
MyModelResponse = MyModel.get_response_schema()

@app.get("/items", response_model=MyModelResponse)
def get_items():
    ...
```

**メリット**:
- スキーマはモジュールインポート時に一度だけ生成
- すべての後続リクエストでキャッシュされる
- ランタイムオーバーヘッドが最小

**デメリット**:
- アプリケーション起動がわずかに遅くなる
- インポート時の依存関係を解決する必要がある

#### 2. 遅延スキーマ生成（非推奨）

```python
@app.get("/items")
def get_items():
    # ❌ 最初のリクエストでのみ生成（その後キャッシュ）
    MyModelResponse = MyModel.get_response_schema()
    return {"response_model": MyModelResponse}
```

**メリット**:
- アプリケーション起動が速い
- 必要になるまで作業を延期

**デメリット**:
- 最初のリクエストが遅い
- インポート/依存関係の問題のデバッグが難しい
- デコレータで `response_model` を使用できない

#### 3. 起動イベントでの生成（代替案）

```python
# FastAPI 起動イベント
@app.on_event("startup")
def generate_schemas():
    # すべてのスキーマを事前生成
    MyModel.get_response_schema()
    OtherModel.get_response_schema()
```

---

## ベストプラクティス

### 1. Column.info の活用

```python
# ✅ Good: 詳細な説明とバリデーション情報
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

# ❌ Bad: info なし
name = Column(String(100), nullable=False, unique=True)
```

### 2. 適切な型アノテーション

```python
# ✅ Good: 具体的な型指定
@BaseModel.response_field(
    total_count=int,
    items="List[ItemResponse]",
    metadata="Dict[str, Any]"
)

# ❌ Bad: すべて Any
@BaseModel.response_field(
    total_count=Any,
    items=Any,
    metadata=Any
)
```

### 3. 前方参照の管理

```python
# ✅ Good: 依存関係を明確に管理
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
# ✅ Good: アプリケーション起動時にスキーマを生成
def initialize_schemas():
    schemas = {}
    schemas['user'] = UserModel.get_response_schema()
    schemas['post'] = PostModel.get_response_schema()
    return schemas

# アプリケーション起動時
app_schemas = initialize_schemas()
```

### 5. 開発環境でのテスト

```python
# 開発環境で先にテスト
EXEC_ENV=dev poetry run python -c "from your_app.models import Task; Task.get_response_schema()"
```

### 6. ログファイルの設定

```python
# アプリケーション起動時にログ設定
import logging

logging.basicConfig(
    level=logging.ERROR,
    filename='data/repom/logs/app.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## トラブルシューティング

### 1. 前方参照エラー

**エラー**: `NameError: name 'SomeResponse' is not defined`

**原因**: カスタム型が文字列として参照されているが、`forward_refs` に提供されていない

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

**原因**: 複合主キーのモデルで `id` カラムが存在しない

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

### 4. 環境に応じたエラーハンドリング

**開発環境**: エラーを即座に検出
```bash
$env:EXEC_ENV='dev'
poetry run python -c "from your_app.models import Task; Task.get_response_schema()"
```

**本番環境**: ログファイルを確認
```bash
# ログファイルの確認
cat data/repom/logs/app.log | grep "Failed to generate"
```

### 5. 循環インポートの問題

**問題**: `ImportError: cannot import name 'X' from partially initialized module`

**解決法**:
```python
# ❌ Bad: 循環インポート
# models/a.py
from models.b import BModel

class AModel(BaseModel):
    ...

# models/b.py
from models.a import AModel  # ← 循環依存

# ✅ Good: 文字列参照を使用
# models/a.py
class AModel(BaseModel):
    @response_field(
        b_items="List[BResponse]"  # 文字列参照
    )
    def to_dict(self):
        ...

# api/schemas.py
from models.a import AModel
from models.b import BModel

BResponse = BModel.get_response_schema()
AResponse = AModel.get_response_schema(
    forward_refs={'BResponse': BResponse}
)
```

---

## 関連ドキュメント

- **BaseRepository & FilterParams**: [repository_and_utilities_guide.md](repository_and_utilities_guide.md)
- **AI コンテキスト管理**: [../technical/ai_context_management.md](../technical/ai_context_management.md)
- **Issue #3 (完了)**: [../issue/completed/003_*.md](../issue/completed/)

---

**作成日**: 2025-11-15  
**最終更新**: 2025-11-15  
**バージョン**: 統合版 v1.0
