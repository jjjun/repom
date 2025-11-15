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

**重要**: 標準型（`List`, `Dict`, `Optional`）は自動解決されるため、カスタム型のみ指定してください。

```python
# ✅ 正しい実装
class ReviewModel(BaseModel):
    @BaseModel.response_field(
        tags=List[str],                        # 標準型：自動解決
        related_books="List[BookResponse]",    # カスタム型：文字列で指定
        parent_item="ParentItemResponse | None"
    )
    def to_dict(self):
        return {
            "tags": ["fiction", "mystery"],
            "related_books": [book.to_dict() for book in self.books],
            "parent_item": self.parent.to_dict() if self.parent else None
        }

# スキーマ生成（カスタム型のみ指定）
BookResponse = BookModel.get_response_schema()
ParentItemResponse = ParentItemModel.get_response_schema()

ResponseSchema = ReviewModel.get_response_schema(
    forward_refs={
        'BookResponse': BookResponse,
        'ParentItemResponse': ParentItemResponse
    }
)
```

### エラーハンドリング

前方参照が解決できない場合、`SchemaGenerationError` 例外が発生し、具体的な解決策を含むエラーメッセージが表示されます。

```python
from repom.base_model import SchemaGenerationError

try:
    schema = Task.get_response_schema(forward_refs={})
except SchemaGenerationError as e:
    print(e)
    # エラーメッセージに未定義型と解決方法が含まれる
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

### use_composite_pk フラグ

複合主キーを使用する場合は `use_composite_pk=True` を設定します。

```python
class TimeBlockModel(BaseModelAuto):
    __tablename__ = "time_blocks"
    
    use_composite_pk = True  # id カラムを使用しない
    use_created_at = True
    use_updated_at = True
    
    date = Column(Date, primary_key=True, info={'description': '日付'})
    start_time = Column(Time, primary_key=True, info={'description': '開始時刻'})
    activity_id = Column(Integer, ForeignKey('time_activities.id'))
```

### フラグの優先順位

1. **use_composite_pk=True**: id カラムを追加しない（複合主キー用）
2. **use_id=True**: id カラムを追加（デフォルト）
3. **use_id=False**: id カラムを追加しない（カスタム主キー用）

---

## 技術詳細: 内部実装

### スキーマ生成フロー

1. **デコレータ実行** (インポート時): `@response_field` が型情報を `to_dict._response_fields` に保存
2. **スキーマ生成** (実行時): `get_response_schema()` を呼び出し
3. **フィールド収集**: SQLAlchemy カラム + `@response_field` の追加フィールド
4. **Pydantic スキーマ作成**: `create_model()` で生成
5. **前方参照解決**: `forward_refs` が指定されている場合、`model_rebuild()` を実行
6. **キャッシュ**: 生成されたスキーマをキャッシュ

### キャッシュ機構

```python
# キャッシュキー形式
cache_key = f"{cls.__name__}::{schema_name}"
if forward_refs:
    cache_key += f"::{','.join(sorted(forward_refs.keys()))}"

# キャッシュ辞書
BaseModel._response_schemas: Dict[str, Type[Any]]
```

### グローバルレジストリ

- **`_EXTRA_FIELDS_REGISTRY`**: `WeakKeyDictionary[type, Dict[str, Any]]`
- メモリリーク防止のため `WeakKeyDictionary` を使用
- モデルクラスが参照されなくなると自動的にクリーンアップ

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
    activities = db.query(TimeActivityModel).all()
    return [activity.to_dict() for activity in activities]

@app.post("/activities/", response_model=TimeActivityResponse, status_code=201)
def create_activity(activity: TimeActivityCreate, db: Session = Depends(get_db)):
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
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity.update_from_dict(updates.dict(exclude_unset=True))
    db.commit()
    db.refresh(activity)
    return activity.to_dict()
```

### スキーマ生成のタイミング

**推奨**: モジュールインポート時に生成

```python
# ✅ 推奨: モジュールレベル
MyModelResponse = MyModel.get_response_schema()

@app.get("/items", response_model=MyModelResponse)
def get_items():
    ...
```

**非推奨**: リクエストごとに生成

```python
# ❌ 非推奨: リクエストごと
@app.get("/items")
def get_items():
    MyModelResponse = MyModel.get_response_schema()  # 遅い
    ...
```

---

## ベストプラクティス

### 1. Column.info を必ず指定

```python
# ✅ 推奨
name = Column(
    String(100), 
    nullable=False,
    info={'description': '活動名（重複不可、最大100文字）'}
)
```

### 2. 具体的な型アノテーション

```python
# ✅ 推奨
@BaseModel.response_field(
    items="List[ItemResponse]",
    metadata="Dict[str, Any]"
)

# ❌ 避ける
@BaseModel.response_field(
    items=Any,
    metadata=Any
)
```

### 3. モジュールレベルでスキーマ生成

```python
# ✅ 推奨: アプリケーション起動時に生成
UserResponse = UserModel.get_response_schema()
PostResponse = PostModel.get_response_schema()
```

---

## トラブルシューティング

### 前方参照エラー

**エラー**: `NameError: name 'SomeResponse' is not defined`

**解決法**:
```python
# 文字列で型を指定し、forward_refs で解決
@BaseModel.response_field(related="List[SomeResponse]")
def to_dict(self):
    ...

schema = MyModel.get_response_schema(
    forward_refs={'SomeResponse': SomeResponse}
)
```

### 複合主キーでの AttributeError

**エラー**: `AttributeError: type object 'MyModel' has no attribute 'id'`

**解決法**: 複合主キーを使用
```python
class MyRepository(BaseRepository[MyModel]):
    def set_find_option(self, query, **kwargs):
        order_by = kwargs.get('order_by', [
            self.model.date.asc(), 
            self.model.time.asc()
        ])
```

### スキーマキャッシュクリア

```python
# 開発中にスキーマが更新されない場合
MyModel._response_schemas.clear()
MyModel._create_schemas.clear()
MyModel._update_schemas.clear()
```

### 循環インポートの回避

```python
# ❌ 避ける: 循環インポート
from models.b import BModel

# ✅ 推奨: 文字列参照
@response_field(b_items="List[BResponse]")
def to_dict(self):
    ...
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
