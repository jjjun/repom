# Repository & Utilities 完全ガイド

**このドキュメントについて**: repom パッケージの BaseRepository、FilterParams、auto_import_models などの基盤機能の完全ガイドです。

## 📚 目次

1. [概要](#概要)
2. [BaseRepository: データアクセス層](#baserepository-データアクセス層)
3. [FilterParams: FastAPI クエリパラメータ統合](#filterparams-fastapi-クエリパラメータ統合)
4. [auto_import_models: モデル自動インポート](#autoimportmodels-モデル自動インポート)
5. [実装パターン集](#実装パターン集)
6. [トラブルシューティング](#トラブルシューティング)

---

## 概要

このガイドでは、repom パッケージが提供する以下の基盤機能について説明します：

### 主な機能

1. **BaseRepository**: データベース操作を抽象化する汎用リポジトリクラス
2. **FilterParams**: FastAPI のクエリパラメータを型安全に扱うクラス
3. **auto_import_models**: モデルファイルを自動的にインポートするユーティリティ

---

## BaseRepository: データアクセス層

### 概要

`BaseRepository` は SQLAlchemy モデルに対する CRUD 操作を提供する汎用リポジトリクラスです。

### 基本的な使い方

```python
from repom.base_repository import BaseRepository
from your_project.models import Task

# リポジトリを作成
repo = BaseRepository(Task)

# ID で取得
task = repo.get_by_id(1)

# 条件で取得
tasks = repo.get_by('status', 'active')

# すべて取得
all_tasks = repo.get_all()

# 保存
new_task = Task(title="新しいタスク")
repo.save(new_task)

# 削除
repo.remove(task)
```

### 提供されるメソッド

#### 取得系メソッド

```python
# ID で取得
task = repo.get_by_id(1)

# カラム名と値で取得
active_tasks = repo.get_by('status', 'active')

# 単一レコードを取得
task = repo.get_by('title', 'Important Task', single=True)

# すべて取得
all_tasks = repo.get_all()

# フィルタ条件で検索
from sqlalchemy import and_
filters = [Task.status == 'active', Task.priority > 5]
tasks = repo.find(filters=filters)

# 単一レコードを検索
task = repo.find_one(filters=[Task.title == 'Specific Task'])

# カウント
total = repo.count(filters=[Task.status == 'active'])
```

#### 保存系メソッド

```python
# 単一保存
task = Task(title="タスク")
repo.save(task)

# dict から保存
repo.dict_save({'title': 'タスク', 'status': 'pending'})

# 複数保存
tasks = [Task(title=f"タスク{i}") for i in range(5)]
repo.saves(tasks)

# dict リストから保存
data_list = [
    {'title': 'タスク1', 'status': 'pending'},
    {'title': 'タスク2', 'status': 'active'}
]
repo.dict_saves(data_list)
```

#### 削除系メソッド

```python
# 削除
task = repo.get_by_id(1)
repo.remove(task)
```

### クエリオプション

`set_find_option` メソッドでページネーションとソートを制御できます。

```python
# offset と limit
tasks = repo.find(
    filters=[Task.status == 'active'],
    offset=10,
    limit=20
)

# ソート（文字列指定）
tasks = repo.find(
    filters=[],
    order_by='created_at:desc'  # 降順
)

tasks = repo.find(
    filters=[],
    order_by='priority:asc'  # 昇順
)

# ソート（SQLAlchemy 式）
from sqlalchemy import desc
tasks = repo.find(
    filters=[],
    order_by=desc(Task.created_at)
)
```

### セキュリティ: ソート可能カラムのホワイトリスト

デフォルトで以下のカラムのみソート可能です：

```python
allowed_order_columns = [
    'id', 'title', 'created_at', 'updated_at',
    'started_at', 'finished_at', 'executed_at'
]
```

**カスタムリポジトリで拡張**:

```python
class TaskRepository(BaseRepository[Task]):
    # ホワイトリストを拡張
    allowed_order_columns = BaseRepository.allowed_order_columns + [
        'priority', 'status', 'assigned_to'
    ]
```

### カスタムリポジトリの作成

```python
from typing import Optional, List
from repom.base_repository import BaseRepository, FilterParams
from your_project.models import Task

class TaskFilterParams(FilterParams):
    """タスク検索パラメータ"""
    keyword: Optional[str] = None
    status: Optional[str] = None
    priority_min: Optional[int] = None

class TaskRepository(BaseRepository[Task]):
    def _build_filters(self, params: Optional[TaskFilterParams]):
        """検索条件を構築"""
        filters = []
        
        if params:
            # キーワード検索
            if params.keyword:
                filters.append(
                    Task.title.ilike(f"%{params.keyword}%")
                )
            
            # ステータス
            if params.status:
                filters.append(Task.status == params.status)
            
            # 優先度
            if params.priority_min:
                filters.append(Task.priority >= params.priority_min)
        
        return filters
    
    def search(self, params: Optional[TaskFilterParams] = None, **kwargs):
        """カスタム検索メソッド"""
        filters = self._build_filters(params)
        return self.find(filters=filters, **kwargs)

# 使用例
repo = TaskRepository(Task)
params = TaskFilterParams(keyword="重要", status="active", priority_min=5)
tasks = repo.search(params, order_by='priority:desc', limit=10)
```

---

## FilterParams: FastAPI クエリパラメータ統合

### 概要

`FilterParams` は FastAPI のクエリパラメータを型安全に扱うための基底クラスです。`as_query_depends()` メソッドを使用すると、OpenAPI ドキュメントに自動的に反映されます。

### 基本的な使い方

```python
from typing import Optional, List
from repom.base_repository import FilterParams

class TaskSearchParams(FilterParams):
    """タスク検索パラメータ"""
    keyword: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None  # 配列型もサポート
    priority_min: Optional[int] = None
    completed: Optional[bool] = None
```

### FastAPI での使用

```python
from fastapi import APIRouter, Depends
from typing import List

router = APIRouter()

@router.get("/tasks", response_model=List[TaskResponse])
def search_tasks(
    params: TaskSearchParams = Depends(TaskSearchParams.as_query_depends())
):
    """
    タスクを検索
    
    クエリパラメータ:
    - keyword: タイトルでキーワード検索
    - status: ステータスでフィルタ（active/pending/completed）
    - tags: タグでフィルタ（複数指定可能）
    - priority_min: 最小優先度
    - completed: 完了済みフラグ
    """
    repo = TaskRepository(Task)
    tasks = repo.search(params)
    return [task.to_dict() for task in tasks]
```

### as_query_depends() の仕組み

`as_query_depends()` は FilterParams を FastAPI の `Query` パラメータに変換します：

```python
# 内部的な動作（概念的表現）
def query_depends(
    keyword: Optional[str] = Query(None, description="Filter by keyword"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    priority_min: Optional[int] = Query(None, description="Filter by priority_min"),
    completed: Optional[bool] = Query(None, description="Filter by completed")
) -> TaskSearchParams:
    return TaskSearchParams(
        keyword=keyword,
        status=status,
        tags=tags,
        priority_min=priority_min,
        completed=completed
    )
```

### OpenAPI ドキュメントへの反映

FastAPI の Swagger UI では、以下のように表示されます：

```
GET /tasks

Query Parameters:
  keyword       string   Filter by keyword
  status        string   Filter by status
  tags          array    Filter by tags (multiple)
  priority_min  integer  Filter by priority_min
  completed     boolean  Filter by completed
```

### セキュリティ: 除外フィールド

`_excluded_from_query` を使用すると、特定のフィールドをクエリパラメータから除外できます。

```python
class SecureTaskSearchParams(FilterParams):
    _excluded_from_query = {'internal_id', 'sensitive_field'}
    
    keyword: Optional[str] = None
    internal_id: Optional[int] = None  # クエリパラメータとして公開されない
    sensitive_field: Optional[str] = None  # クエリパラメータとして公開されない

# プライベートフィールド（_で始まる）も自動的に除外
class AutoSecureParams(FilterParams):
    keyword: Optional[str] = None
    _internal_id: Optional[int] = None  # 自動的に除外
```

### カスタム description の指定

```python
from pydantic import Field

class TaskSearchParams(FilterParams):
    keyword: Optional[str] = Field(
        default=None,
        description="タイトルまたは説明でキーワード検索"
    )
    status: Optional[str] = Field(
        default=None,
        description="ステータスでフィルタ（active/pending/completed）"
    )
```

### 配列型のクエリパラメータ

```python
class TaskSearchParams(FilterParams):
    tags: Optional[List[str]] = None  # /tasks?tags=work&tags=urgent

# FastAPI での使用
# GET /tasks?tags=work&tags=urgent
# → tags=['work', 'urgent']
```

---

## auto_import_models: モデル自動インポート

### 概要

`auto_import_models` は models ディレクトリ内のすべてのモデルファイルを自動的にインポートするユーティリティ関数です。`__init__.py` で手動でインポートを管理する必要がなくなります。

### 基本的な使い方

```python
# your_project/models/__init__.py
from pathlib import Path
from repom.utility import auto_import_models

# このディレクトリ内のすべてのモデルを自動インポート
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models'  # パッケージ名を指定
)
```

これだけで完了です！新しいモデルを作成しても、手動でインポートを追加する必要はありません。

### 動作の仕組み

1. **ディレクトリをスキャン**: models ディレクトリを再帰的にスキャン
2. **ファイルをフィルタ**: ユーティリティディレクトリとプライベートファイルをスキップ
3. **アルファベット順にソート**: 一貫したインポート順序を保証
4. **モジュールをインポート**: 各モデルファイルをロード
5. **キャッシュを使用**: Python のインポートキャッシュで重複ロードを防止

### ディレクトリ構造

#### プロジェクト構造の例

```
your_project/
└── models/
    ├── __init__.py           # auto_import_models をここで呼び出す
    ├── user.py               # ✅ インポートされる
    ├── product.py            # ✅ インポートされる
    ├── base/                 # ❌ 除外（ユーティリティディレクトリ）
    │   ├── helper.py
    │   └── mixins.py
    ├── validators/           # ❌ 除外（ユーティリティディレクトリ）
    │   └── email.py
    └── admin/                # ✅ サブディレクトリのモデルもインポート
        ├── user.py           # ✅ your_project.models.admin.user としてインポート
        └── settings.py       # ✅ your_project.models.admin.settings としてインポート
```

#### デフォルトで除外されるディレクトリ

以下のディレクトリは自動的に除外されます：
- `base/` - 基底クラスとヘルパー
- `mixin/` - Mixin クラス
- `validators/` - バリデーションユーティリティ
- `utils/` - ユーティリティ関数
- `helpers/` - ヘルパー関数
- `__pycache__/` - Python キャッシュ

### カスタム除外

```python
from pathlib import Path
from repom.utility import auto_import_models

# 追加のディレクトリを除外
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'base', 'mixin', 'validators', 'tests', 'fixtures'}
)
```

### 最小限の除外

```python
from pathlib import Path
from repom.utility import auto_import_models

# __pycache__ のみ除外
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'__pycache__'}
)
```

### モデルの依存関係

モデル A がモデル B に依存している場合、2つの方法があります：

#### 方法1: ファイル命名（推奨）

```
models/
├── 01_user.py      # 最初にインポート
└── 02_profile.py   # 2番目にインポート（user に依存）
```

#### 方法2: モデルファイル内で明示的にインポート

```python
# models/profile.py
from your_project.models.user import User  # 明示的な依存関係

class Profile(BaseModel):
    __tablename__ = 'profiles'
    user_id = Column(Integer, ForeignKey(User.id))
```

### メリット

✅ **手動メンテナンス不要**: モデルを追加しても `__init__.py` を更新する必要なし  
✅ **一貫したインポート順序**: アルファベット順でソートされ予測可能  
✅ **サブディレクトリサポート**: ネストされたフォルダでモデルを整理可能  
✅ **ユーティリティ除外**: ヘルパーコードをモデルから分離  
✅ **エラーハンドリング**: インポート失敗時の警告表示  
✅ **パフォーマンス**: Python のインポートキャッシュを使用（重複なし）

### Alembic との統合

Alembic マイグレーションと併用する場合、`alembic/env.py` でモデルロードフックを呼び出します：

```python
from your_project.config import load_set_model_hook_function

# これが auto_import_models をトリガーする
load_set_model_hook_function()
```

### トラブルシューティング

#### モデルが検出されない

1. ファイル名が `_`（アンダースコア）で始まっていないか確認
2. ファイルが除外ディレクトリにないか確認
3. ファイルが `.py` 拡張子を持っているか確認
4. モデルファイルにインポートエラーがないか確認

#### インポートエラー

以下のような警告が表示される場合：
```
Warning: Failed to import your_project.models.example: <error>
```

特定のモデルファイルで構文エラーや依存関係エラーがないか確認してください。

### 実装例

```python
# your_project/models/__init__.py
"""
SQLAlchemy メタデータ登録のためにすべてのモデルを自動インポート
"""
from pathlib import Path
from repom.utility import auto_import_models

# ユーティリティとテストを除くすべてのモデルをインポート
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'base', 'mixin', 'validators', 'tests', '__pycache__'}
)

# オプション: 便利なように特定のモデルをエクスポート
from your_project.models.user import User
from your_project.models.product import Product

__all__ = ['User', 'Product']
```

---

## 実装パターン集

### パターン1: 基本的な CRUD API

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

router = APIRouter()

# スキーマ生成
TaskResponse = TaskModel.get_response_schema()
TaskCreate = TaskModel.get_create_schema()
TaskUpdate = TaskModel.get_update_schema()

# リポジトリ
class TaskRepository(BaseRepository[TaskModel]):
    pass

@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    repo = TaskRepository(TaskModel, db)
    tasks = repo.get_all()
    return [task.to_dict() for task in tasks]

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    repo = TaskRepository(TaskModel, db)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()

@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    repo = TaskRepository(TaskModel, db)
    task = repo.dict_save(data.dict())
    return task.to_dict()

@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    repo = TaskRepository(TaskModel, db)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.update_from_dict(data.dict(exclude_unset=True))
    db.commit()
    db.refresh(task)
    return task.to_dict()

@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    repo = TaskRepository(TaskModel, db)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    repo.remove(task)
```

### パターン2: 検索機能付き API

```python
from fastapi import APIRouter, Depends
from typing import List, Optional

router = APIRouter()

# FilterParams 定義
class TaskSearchParams(FilterParams):
    keyword: Optional[str] = Field(None, description="キーワード検索")
    status: Optional[str] = Field(None, description="ステータス")
    tags: Optional[List[str]] = Field(None, description="タグ")
    priority_min: Optional[int] = Field(None, description="最小優先度")
    assigned_to: Optional[int] = Field(None, description="担当者ID")

# リポジトリ
class TaskRepository(BaseRepository[TaskModel]):
    def _build_filters(self, params: Optional[TaskSearchParams]):
        filters = []
        
        if params:
            if params.keyword:
                filters.append(
                    or_(
                        TaskModel.title.ilike(f"%{params.keyword}%"),
                        TaskModel.description.ilike(f"%{params.keyword}%")
                    )
                )
            
            if params.status:
                filters.append(TaskModel.status == params.status)
            
            if params.tags:
                # JSON 配列に含まれるタグで検索
                for tag in params.tags:
                    filters.append(TaskModel.tags.contains([tag]))
            
            if params.priority_min:
                filters.append(TaskModel.priority >= params.priority_min)
            
            if params.assigned_to:
                filters.append(TaskModel.assigned_to == params.assigned_to)
        
        return filters

@router.get("/tasks/search", response_model=List[TaskResponse])
def search_tasks(
    params: TaskSearchParams = Depends(TaskSearchParams.as_query_depends()),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    タスクを検索
    
    OpenAPI ドキュメントに自動的に反映されます
    """
    repo = TaskRepository(TaskModel, db)
    filters = repo._build_filters(params)
    
    offset = (page - 1) * page_size
    tasks = repo.find(
        filters=filters,
        offset=offset,
        limit=page_size,
        order_by='created_at:desc'
    )
    
    return [task.to_dict() for task in tasks]
```

### パターン3: ページネーション対応

```python
from pydantic import BaseModel as PydanticBaseModel
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginatedResponse(PydanticBaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

@router.get("/tasks", response_model=PaginatedResponse[TaskResponse])
def list_tasks_paginated(
    params: TaskSearchParams = Depends(TaskSearchParams.as_query_depends()),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    repo = TaskRepository(TaskModel, db)
    filters = repo._build_filters(params)
    
    # 総数を取得
    total = repo.count(filters=filters)
    
    # ページネーション
    offset = (page - 1) * page_size
    tasks = repo.find(
        filters=filters,
        offset=offset,
        limit=page_size,
        order_by='created_at:desc'
    )
    
    return {
        'items': [task.to_dict() for task in tasks],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size
    }
```

---

## トラブルシューティング

### 1. ソート可能カラムエラー

**エラー**: `ValueError: Column 'custom_field' is not allowed for sorting`

**原因**: ホワイトリストに含まれていないカラムでソートしようとした

**解決法**:
```python
class TaskRepository(BaseRepository[TaskModel]):
    # ホワイトリストを拡張
    allowed_order_columns = BaseRepository.allowed_order_columns + [
        'custom_field'
    ]
```

### 2. FilterParams が OpenAPI に表示されない

**問題**: クエリパラメータが Swagger UI に表示されない

**原因**: `as_query_depends()` を使用していない

**解決法**:
```python
# ❌ Bad
@router.get("/tasks")
def search_tasks(params: TaskSearchParams):  # これでは表示されない
    ...

# ✅ Good
@router.get("/tasks")
def search_tasks(
    params: TaskSearchParams = Depends(TaskSearchParams.as_query_depends())
):
    ...
```

### 3. auto_import_models でモデルが見つからない

**問題**: 一部のモデルがインポートされない

**原因**:
- ファイル名が `_` で始まっている
- 除外ディレクトリに配置されている
- インポートエラーが発生している

**解決法**:
```python
# ファイル名を確認
models/
├── user.py        # ✅ OK
├── _private.py    # ❌ 除外される
└── test_model.py  # ❌ tests/ ディレクトリなら除外

# 除外設定を確認
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'__pycache__'}  # 必要最小限に
)
```

### 4. リポジトリのトランザクション管理

**問題**: 複数の操作をアトミックに実行したい

**解決法**:
```python
from repom.db import db_session

# コンテキストマネージャを使用
with db_session() as session:
    repo = TaskRepository(TaskModel, session)
    
    # 複数の操作
    task1 = repo.dict_save({'title': 'タスク1'})
    task2 = repo.dict_save({'title': 'タスク2'})
    
    # すべて成功した場合のみコミット
    session.commit()
```

---

## 関連ドキュメント

- **BaseModelAuto & スキーマ生成**: [base_model_auto_guide.md](base_model_auto_guide.md)
- **AI コンテキスト管理**: [../technical/ai_context_management.md](../technical/ai_context_management.md)
- **メインドキュメント**: [../../README.md](../../README.md)

---

**作成日**: 2025-11-15  
**最終更新**: 2025-11-15  
**バージョン**: 統合版 v1.0
