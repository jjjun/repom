# BaseRepository ガイド

**目的**: repom の `BaseRepository` によるデータアクセスパターンを理解する

**対象読者**: repom を使ってリポジトリパターンを実装する開発者・AI エージェント

---

## 📚 目次

1. [基本的な使い方](#基本的な使い方)
2. [CRUD 操作](#crud-操作)
3. [検索とフィルタリング](#検索とフィルタリング)
4. [FilterParams と FastAPI 統合](#filterparams-と-fastapi-統合)
5. [カスタムリポジトリ](#カスタムリポジトリ)
6. [実装パターン](#実装パターン)

---

## 基本的な使い方

### リポジトリの作成

```python
from repom.base_repository import BaseRepository
from your_project.models import Task

# 基本的な使い方
repo = BaseRepository(Task)

# カスタムセッションを使用
from repom.db import db_session
repo = BaseRepository(Task, session=db_session)
```

### 主要メソッド一覧

| メソッド | 用途 | 戻り値 |
|---------|------|--------|
| `get_by_id(id)` | ID で取得 | `Optional[T]` |
| `get_by(column, value)` | カラムで検索 | `List[T]` |
| `get_all()` | 全件取得 | `List[T]` |
| `find(filters, **options)` | 条件検索 | `List[T]` |
| `find_one(filters)` | 単一検索 | `Optional[T]` |
| `count(filters)` | 件数カウント | `int` |
| `save(instance)` | 保存 | `T` |
| `saves(instances)` | 一括保存 | `None` |
| `remove(instance)` | 削除 | `None` |

---

## CRUD 操作

### Create（作成）

```python
# 1件保存
task = Task(title="新しいタスク", status="active")
saved_task = repo.save(task)

# 辞書から保存
task = repo.dict_save({"title": "タスク2", "status": "pending"})

# 複数保存
tasks = [Task(title=f"タスク{i}") for i in range(3)]
repo.saves(tasks)

# 辞書リストから保存
data_list = [{"title": f"タスク{i}"} for i in range(3)]
repo.dict_saves(data_list)
```

### Read（取得）

```python
# ID で取得
task = repo.get_by_id(1)

# カラムで検索（複数件）
active_tasks = repo.get_by('status', 'active')

# 単一取得（single=True）
task = repo.get_by('title', 'タスク1', single=True)

# 全件取得
all_tasks = repo.get_all()
```

### Update（更新）

```python
# インスタンスを取得して更新
task = repo.get_by_id(1)
task.status = 'completed'
repo.save(task)

# または BaseModel の update_from_dict を使用
task.update_from_dict({"status": "completed"})
repo.save(task)
```

### Delete（削除）

```python
task = repo.get_by_id(1)
repo.remove(task)
```

---

## 検索とフィルタリング

### find() メソッド

```python
from sqlalchemy import and_, or_

# 基本的な検索
tasks = repo.find()  # 全件

# フィルタ条件付き
filters = [Task.status == 'active']
tasks = repo.find(filters=filters)

# 複数条件（AND）
filters = [
    Task.status == 'active',
    Task.priority == 'high'
]
tasks = repo.find(filters=filters)

# OR 条件
filters = [
    or_(
        Task.status == 'active',
        Task.status == 'pending'
    )
]
tasks = repo.find(filters=filters)
```

### ページネーション

```python
# offset と limit
tasks = repo.find(offset=0, limit=10)

# 2ページ目（1ページ10件）
tasks = repo.find(offset=10, limit=10)
```

### ソート

```python
# デフォルト: id 昇順
tasks = repo.find()

# 文字列指定（簡易）
tasks = repo.find(order_by='created_at:desc')
tasks = repo.find(order_by='title:asc')

# SQLAlchemy 式
from sqlalchemy import desc
tasks = repo.find(order_by=desc(Task.created_at))

# 複数ソート（カスタムリポジトリで実装）
class TaskRepository(BaseRepository[Task]):
    def find_sorted(self):
        query = select(Task).order_by(
            desc(Task.priority),
            Task.created_at
        )
        return self.session.execute(query).scalars().all()
```

### ソート可能なカラムの制限

セキュリティのため、ソート可能なカラムは `allowed_order_columns` で制限されています。

```python
# デフォルトで許可されているカラム
BaseRepository.allowed_order_columns = [
    'id', 'title', 'created_at', 'updated_at',
    'started_at', 'finished_at', 'executed_at'
]

# カスタムリポジトリで拡張
class TaskRepository(BaseRepository[Task]):
    allowed_order_columns = BaseRepository.allowed_order_columns + [
        'priority', 'status'
    ]
```

### 件数カウント

```python
# 全件数
total = repo.count()

# 条件付きカウント
filters = [Task.status == 'active']
active_count = repo.count(filters=filters)
```

---

## FilterParams と FastAPI 統合

### 基本的な FilterParams

```python
from repom.base_repository import FilterParams
from typing import Optional

class TaskFilterParams(FilterParams):
    status: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None
```

### FastAPI での使用

```python
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/tasks")
def list_tasks(
    filter_params: TaskFilterParams = Depends(TaskFilterParams.as_query_depends())
):
    # filter_params を使ってリポジトリで検索
    repo = TaskRepository()
    tasks = repo.find_by_params(filter_params)
    return tasks
```

**クエリ例**:
```
GET /tasks?status=active&priority=high
```

### セキュリティ：除外フィールド

```python
class SecureFilterParams(FilterParams):
    # 公開フィールド
    status: Optional[str] = None
    
    # 除外フィールド（クエリパラメータから隠す）
    _excluded_from_query = {"internal_id", "secret_field"}
    internal_id: Optional[int] = None  # 除外される
    secret_field: Optional[str] = None  # 除外される
```

**動作**:
- `_excluded_from_query` に指定されたフィールドは `as_query_depends()` から除外
- プライベートフィールド（`_`で始まる）も自動的に除外

### カスタムリポジトリで FilterParams を処理

```python
class TaskRepository(BaseRepository[Task]):
    def _build_filters(self, params: Optional[TaskFilterParams]) -> list:
        """FilterParams から SQLAlchemy フィルタを構築"""
        if not params:
            return []
        
        filters = []
        
        if params.status:
            filters.append(Task.status == params.status)
        
        if params.priority:
            filters.append(Task.priority == params.priority)
        
        if params.title:
            # 部分一致検索
            filters.append(Task.title.like(f"%{params.title}%"))
        
        return filters
    
    def find_by_params(
        self,
        params: Optional[TaskFilterParams] = None,
        **kwargs
    ) -> List[Task]:
        """FilterParams を使って検索"""
        filters = self._build_filters(params)
        return self.find(filters=filters, **kwargs)
    
    def count_by_params(self, params: Optional[TaskFilterParams] = None) -> int:
        """FilterParams を使ってカウント"""
        filters = self._build_filters(params)
        return self.count(filters=filters)
```

---

## カスタムリポジトリ

### 基本的なカスタムリポジトリ

```python
class TaskRepository(BaseRepository[Task]):
    def find_active(self) -> List[Task]:
        """アクティブなタスクを取得"""
        return self.get_by('status', 'active')
    
    def find_by_priority(self, priority: str) -> List[Task]:
        """優先度で検索"""
        return self.get_by('priority', priority)
    
    def count_active(self) -> int:
        """アクティブなタスクをカウント"""
        filters = [Task.status == 'active']
        return self.count(filters=filters)
```

### 複雑な検索ロジック

```python
from sqlalchemy import and_, or_, select

class TaskRepository(BaseRepository[Task]):
    def find_urgent_tasks(self) -> List[Task]:
        """緊急タスク（高優先度 かつ 期限間近）"""
        from datetime import datetime, timedelta
        
        deadline = datetime.now() + timedelta(days=3)
        
        filters = [
            Task.priority == 'high',
            Task.due_date <= deadline,
            Task.status != 'completed'
        ]
        
        return self.find(filters=filters, order_by='due_date:asc')
    
    def find_overdue_tasks(self) -> List[Task]:
        """期限切れタスク"""
        from datetime import datetime
        
        query = select(Task).where(
            and_(
                Task.due_date < datetime.now(),
                Task.status != 'completed'
            )
        ).order_by(Task.due_date)
        
        return self.session.execute(query).scalars().all()
```

### 関連モデルの操作

```python
class TaskRepository(BaseRepository[Task]):
    def find_with_user(self, user_id: int) -> List[Task]:
        """特定ユーザーのタスクを取得"""
        return self.get_by('user_id', user_id)
    
    def find_by_tags(self, tags: List[str]) -> List[Task]:
        """タグで検索（多対多）"""
        query = select(Task).join(Task.tags).where(
            Tag.name.in_(tags)
        ).distinct()
        
        return self.session.execute(query).scalars().all()
```

---

## 実装パターン

### パターン1: シンプルな CRUD

```python
# リポジトリ定義
class UserRepository(BaseRepository[User]):
    pass

# 使用例
repo = UserRepository()

# 作成
user = repo.dict_save({"name": "太郎", "email": "taro@example.com"})

# 取得
user = repo.get_by_id(1)
users = repo.get_by('email', 'taro@example.com')

# 更新
user.name = "太郎2"
repo.save(user)

# 削除
repo.remove(user)
```

### パターン2: FilterParams + FastAPI

```python
# FilterParams 定義
class UserFilterParams(FilterParams):
    name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

# リポジトリ定義
class UserRepository(BaseRepository[User]):
    def _build_filters(self, params: Optional[UserFilterParams]) -> list:
        if not params:
            return []
        
        filters = []
        if params.name:
            filters.append(User.name.like(f"%{params.name}%"))
        if params.email:
            filters.append(User.email == params.email)
        if params.is_active is not None:
            filters.append(User.is_active == params.is_active)
        
        return filters
    
    def find_by_params(self, params: Optional[UserFilterParams] = None, **kwargs):
        filters = self._build_filters(params)
        return self.find(filters=filters, **kwargs)

# FastAPI エンドポイント
@router.get("/users")
def list_users(
    filter_params: UserFilterParams = Depends(UserFilterParams.as_query_depends()),
    offset: int = 0,
    limit: int = 10
):
    repo = UserRepository()
    users = repo.find_by_params(filter_params, offset=offset, limit=limit)
    total = repo.count_by_params(filter_params)
    
    return {
        "items": [user.to_dict() for user in users],
        "total": total,
        "offset": offset,
        "limit": limit
    }
```

### パターン3: ビジネスロジック統合

```python
class OrderRepository(BaseRepository[Order]):
    def create_order(self, user_id: int, items: List[dict]) -> Order:
        """注文を作成（ビジネスロジック）"""
        # 合計金額を計算
        total = sum(item['price'] * item['quantity'] for item in items)
        
        # 注文を作成
        order = Order(
            user_id=user_id,
            status='pending',
            total_amount=total
        )
        
        return self.save(order)
    
    def complete_order(self, order_id: int) -> Order:
        """注文を完了"""
        order = self.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status != 'pending':
            raise ValueError(f"Order {order_id} is already {order.status}")
        
        order.status = 'completed'
        order.completed_at = datetime.now()
        
        return self.save(order)
    
    def cancel_order(self, order_id: int) -> Order:
        """注文をキャンセル"""
        order = self.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status == 'completed':
            raise ValueError("Cannot cancel completed order")
        
        order.status = 'cancelled'
        order.cancelled_at = datetime.now()
        
        return self.save(order)
```

---

## トラブルシューティング

### よくあるエラー

#### 1. `AttributeError: Column '...' does not exist`

```python
# ❌ 間違い
tasks = repo.get_by('wrong_column', 'value')

# ✅ 正しい
tasks = repo.get_by('status', 'active')
```

**解決方法**: モデルに存在するカラム名を使用する

#### 2. `ValueError: Column '...' is not allowed for sorting`

```python
# ❌ 許可されていないカラムでソート
tasks = repo.find(order_by='custom_field:desc')

# ✅ allowed_order_columns を拡張
class TaskRepository(BaseRepository[Task]):
    allowed_order_columns = BaseRepository.allowed_order_columns + ['custom_field']
```

#### 3. セッションエラー

```python
# ❌ セッションが閉じている
repo = TaskRepository()
# ... 長時間経過 ...
task = repo.get_by_id(1)  # エラー

# ✅ 新しいセッションを使用
from repom.db import db_session
repo = TaskRepository(session=db_session)
```

### デバッグのヒント

```python
# クエリをログ出力
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# フィルタを確認
filters = repo._build_filters(params)
print(f"Filters: {filters}")

# 件数を確認してからデータ取得
count = repo.count(filters=filters)
print(f"Found {count} records")
if count > 0:
    results = repo.find(filters=filters)
```

---

## 関連ドキュメント

- **[auto_import_models ガイド](auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseModelAuto ガイド](base_model_auto_guide.md)**: スキーマ自動生成
- **[BaseRepository ソースコード](../../repom/base_repository.py)**: 実装の詳細

---

**最終更新**: 2025-11-16  
**対象バージョン**: repom v2.0+
