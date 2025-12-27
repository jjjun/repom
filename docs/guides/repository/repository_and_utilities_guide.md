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

#### 推奨パターン: カスタム __init__ を定義

※ `repom.base_repository` からのインポートは非推奨で DeprecationWarning が出るため、`repom.repositories` から読み込んでください。

```python
from repom.repositories import BaseRepository
from your_project.models import Task
from sqlalchemy.orm import Session

# カスタムリポジトリを定義（推奨）
class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)

# インスタンス化（モデル名の指定が不要）
repo = TaskRepository(session=db_session)
```

**メリット**:
- インスタンス化時にモデル名を省略できる
- カスタムメソッドを追加しやすい
- コードが読みやすい

#### 代替パターン: BaseRepository を直接使用

```python
from repom.repositories import BaseRepository
from your_project.models import Task

# カスタムリポジトリが不要な場合
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

# 関連モデルも一緒に取得（N+1 問題を回避）
from sqlalchemy.orm import selectinload, joinedload
task = repo.get_by_id(1, options=[
    joinedload(Task.user),        # ユーザー情報を JOIN
    selectinload(Task.comments)   # コメントを一括取得
])

# カラムで検索（複数件）
active_tasks = repo.get_by('status', 'active')

# カラムで検索 + 関連モデル取得
active_tasks = repo.get_by('status', 'active', options=[
    joinedload(Task.user)
])

# 単一取得（single=True）
task = repo.get_by('title', 'タスク1', single=True)

# 単一取得 + 関連モデル
task = repo.get_by('title', 'タスク1', single=True, options=[
    joinedload(Task.user)
])

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

### find_by_ids() メソッド - 効率的な一括取得

**N+1 問題の解決に最適**

```python
# N+1 問題を避ける（❌ 悪い例）
for task_id in task_ids:
    task = repo.get_by_id(task_id)  # N回のクエリ！
    # ... 処理

# 一括取得で解決（✅ 良い例）
tasks = repo.find_by_ids(task_ids)  # 1回のクエリ
task_dict = {task.id: task for task in tasks}
for task_id in task_ids:
    task = task_dict.get(task_id)
    # ... 処理
```

**基本的な使い方**

```python
# 複数IDで一括取得
ids = [1, 2, 3]
tasks = repo.find_by_ids(ids)  # List[Task]

# 空リスト
tasks = repo.find_by_ids([])  # []

# 存在しないIDは無視される
tasks = repo.find_by_ids([1, 999, 3])  # ID 999は取得されない

# 重複IDは自動で除外
tasks = repo.find_by_ids([1, 1, 2])  # IDが1のレコードは1つだけ
```

**ソフトデリート対応**

```python
# 論理削除されたレコードも含める
tasks = repo.find_by_ids([1, 2, 3], include_deleted=True)

# デフォルトは論理削除を除外
tasks = repo.find_by_ids([1, 2, 3])  # include_deleted=False
```

**注意事項**

- 返却順序は保証されません（必要な場合はアプリケーション側でソート）
- 大量のIDを指定する場合、データベースの制限に注意
- connection poolの設定は `repom.config.RepomConfig.engine_kwargs` で調整可能

### Eager Loading（N+1 問題の解決）

**関連モデルの効率的な取得**

SQLAlchemy の `options` パラメータを使用して、N+1 問題を解決できます。

**対応メソッド**:
- ✅ `find()` - 複数レコード取得
- ✅ `find_one()` - 単一レコード取得
- ✅ `get_by_id()` - ID で単一レコード取得
- ✅ `get_by()` - カラム条件で取得（単一/複数両対応）

#### 基本的な使い方

```python
from sqlalchemy.orm import joinedload, selectinload

# find() で使用
tasks = repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]
)

# get_by_id() で使用
task = repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])

# get_by() で使用（単一取得）
task = repo.get_by('title', 'タスク1', single=True, options=[
    joinedload(Task.user)
])

# get_by() で使用（複数取得）
tasks = repo.get_by('status', 'active', options=[
    selectinload(Task.comments)
])

# find_one() で使用
task = repo.find_one(
    filters=[Task.id == 1],
    options=[joinedload(Task.user)]
)
```

#### joinedload - 1対1 / 多対1 に最適

```python
from sqlalchemy.orm import joinedload

# 基本的な使い方
tasks = repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]  # user を JOIN で取得
)

# N+1 なしでアクセス可能
for task in tasks:
    print(task.user.name)  # 追加のクエリなし
```

**SQL例**:
```sql
SELECT tasks.*, users.*
FROM tasks
LEFT OUTER JOIN users ON users.id = tasks.user_id
WHERE tasks.status = 'active';
```

#### selectinload - 1対多 / 多対多 に最適

```python
from sqlalchemy.orm import selectinload

# コレクション（1対多）を効率的に取得
users = user_repo.find(
    options=[selectinload(User.tasks)]  # 関連するタスクを取得
)

# N+1 なしでアクセス可能
for user in users:
    for task in user.tasks:  # 追加のクエリなし
        print(task.title)
```

**SQL例**:
```sql
-- 1. ユーザーを取得
SELECT * FROM users;

-- 2. 関連するタスクを一括取得（IN句）
SELECT * FROM tasks WHERE user_id IN (1, 2, 3, ...);
```

#### 複数の関連モデルを同時に取得

```python
tasks = repo.find(
    options=[
        joinedload(Task.user),        # 1対1
        selectinload(Task.tags),      # 1対多
        selectinload(Task.comments)   # 1対多
    ]
)
```

#### ネストした関連モデル

```python
# task → user → department
tasks = repo.find(
    options=[
        joinedload(Task.user).joinedload(User.department)
    ]
)

for task in tasks:
    print(task.user.department.name)  # N+1 なし
```

#### カスタムリポジトリで利用

```python
class TaskRepository(BaseRepository[Task]):
    def find_with_user(self, **kwargs):
        """ユーザー情報を含めて取得"""
        return self.find(
            options=[joinedload(Task.user)],
            **kwargs
        )
    
    def find_full(self, **kwargs):
        """すべての関連情報を含めて取得"""
        return self.find(
            options=[
                joinedload(Task.user),
                selectinload(Task.tags),
                selectinload(Task.comments)
            ],
            **kwargs
        )
```

#### ベストプラクティス

| パターン | 使用する options | 理由 |
|---------|-----------------|------|
| 1対1 / 多対1 | `joinedload` | 1回のクエリで完結 |


---

### デフォルト Eager Loading（default_options）

**NEW in v1.x**: コンストラクタで `default_options` を設定することで、リポジトリのすべての取得メソッドで自動的に eager loading を適用できます。

#### 基本的な使い方

```python
from sqlalchemy.orm import joinedload, selectinload

class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)
        # デフォルトで user と comments を eager load
        self.default_options = [
            joinedload(Task.user),
            selectinload(Task.comments)
        ]

# 使用例
repo = TaskRepository(session=db_session)

# options を指定しなくても自動的に eager loading される
tasks = repo.find()  # user と comments がロード済み
task = repo.get_by_id(1)  # 同じく自動適用
```

#### 影響を受けるメソッド

`default_options` は以下のメソッドで自動的に適用されます：

- ✅ `find()` - 複数レコード取得
- ✅ `find_one()` - 単一レコード取得
- ✅ `get_by_id()` - ID で取得
- ✅ `get_by()` - カラム条件で取得

#### options の優先順位

```python
# 1. options=None（デフォルト）→ default_options を使用
tasks = repo.find()  # default_options が適用される

# 2. options=[] （空リスト）→ eager loading なし
tasks = repo.find(options=[])  # default_options をスキップ

# 3. options=[...] （明示指定）→ 指定した options を使用
tasks = repo.find(options=[
    selectinload(Task.tags)  # default_options は無視される
])
```

#### パフォーマンスへの影響

**メリット（N+1 問題の解決）**:

```python
# Without default_options
tasks = repo.find()  # 1回のクエリ
for task in tasks:
    print(task.user.name)  # N回のクエリ（N+1 問題）
# 合計: 1 + N = 101回のクエリ（N=100の場合）

# With default_options
class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)
        self.default_options = [joinedload(Task.user)]

tasks = repo.find()  # 2回のクエリ（tasks と users）
for task in tasks:
    print(task.user.name)  # クエリなし
# 合計: 2回のクエリ（N=100でも同じ）
```

**デメリット（不要な eager load）**:

リレーションを使わない場合でも eager load が発生します。その場合は `options=[]` で無効化できます：

```python
# リレーション不要な場合は明示的にスキップ
task_ids = [task.id for task in repo.find(options=[])]  # 高速
```

#### 実用例

```python
# 例1: FastAPI での使用
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)
        self.default_options = [
            joinedload(Task.user),
            selectinload(Task.tags)
        ]

@router.get("/tasks")
def get_tasks(session: Session = Depends(get_db_session)):
    repo = TaskRepository(session=session)
    return repo.find()  # 自動的に user と tags をロード

# 例2: リレーション不要な場合は無効化
@router.get("/tasks/ids")
def get_task_ids(session: Session = Depends(get_db_session)):
    repo = TaskRepository(session=session)
    tasks = repo.find(options=[])  # eager loading なし
    return [task.id for task in tasks]
```

#### ベストプラクティス

| 状況 | 推奨設定 | 理由 |
|------|---------|------|
| リレーションを頻繁に使う | `default_options` で設定 | N+1 問題を自動的に回避 |
| リレーションをたまに使う | `default_options` なし | 必要に応じて `options` を指定 |
| パフォーマンスが重要 | ケースバイケースで `options` を指定 | 柔軟な最適化 |

---
| 1対多 / 多対多 | `selectinload` | カルテシアン積を避ける |
| 深いネスト | `joinedload().joinedload()` | チェーンで接続 |
| 条件付き取得 | `contains_eager` | フィルタ付き JOIN |

#### パフォーマンス比較

```python
# ❌ N+1 問題（101回のクエリ）
tasks = repo.find()  # 1回
for task in tasks:   # 100件
    user = task.user # 100回のクエリ

# ✅ joinedload（1回のクエリ）
tasks = repo.find(options=[joinedload(Task.user)])
for task in tasks:
    user = task.user # クエリなし

# ✅ selectinload（2回のクエリ）
tasks = repo.find(options=[selectinload(Task.tags)])
for task in tasks:
    tags = task.tags # クエリなし

# ❌ get_by_id() で N+1 問題
task = repo.get_by_id(1)
user = task.user      # 追加クエリ発生
comments = task.comments  # 追加クエリ発生

# ✅ get_by_id() + options で解決
task = repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])
user = task.user      # クエリなし
comments = task.comments  # クエリなし
```

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
この設定と `parse_order_by()` / `set_find_option()` は `QueryBuilderMixin`
（`BaseRepository` / `AsyncBaseRepository` で共通継承）にまとめられており、
同期・非同期の両方で同じロジックが適用されます。

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
from repom.repositories import FilterParams
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

- **[auto_import_models ガイド](../core/auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseModelAuto ガイド](../core/base_model_auto_guide.md)**: スキーマ自動生成
- **[BaseRepository ソースコード](../../repom/repositories/base_repository.py)**: 実装の詳細

---

**最終更新**: 2025-11-16  
**対象バージョン**: repom v2.0+
