# Repository 上級ガイド（検索・フィルタ・options）

**目的**: 複雑な検索、パフォーマンス最適化、カスタムリポジトリの実装

**対象読者**: 複雑な検索機能やパフォーマンス最適化が必要な開発者・AI エージェント

**前提**: このガイドは非同期コード（`AsyncBaseRepository`）を使用しています。同期版（`BaseRepository`）も同様に動作しますが、`await` を削除してください。

**関連ドキュメント**:
- [基礎編：CRUD操作](base_repository_guide.md) - リポジトリの基本的な使い方
- [FastAPI 統合編：FilterParams](repository_filter_params_guide.md) - FastAPI での検索パラメータ処理
- [非同期版](async_repository_guide.md) - AsyncBaseRepository 固有の機能と並行処理など

---

## 📚 目次

1. [検索とフィルタリング](#検索とフィルタリング)
2. [Eager Loading（N+1問題の解決）](#eager-loadingn1問題の解決)
3. [カスタムリポジトリ](#カスタムリポジトリ)
4. [実装パターン：ビジネスロジックとの統合](#実装パターンビジネスロジックとの統合)

---

## 検索とフィルタリング

### find_by_ids() メソッド - 効率的な一括取得

**N+1 問題の解決に最適**

```python
# N+1 問題を避ける（❌ 悪い例）
for task_id in task_ids:
    task = await repo.get_by_id(task_id)  # N回のクエリ
    # ... 処理

# 一括取得で解決（✅ 良い例）
tasks = await repo.find_by_ids(task_ids)  # 1回のクエリ
task_dict = {task.id: task for task in tasks}
for task_id in task_ids:
    task = task_dict.get(task_id)
    # ... 処理
```

**基本的な使い方**

```python
# 複数IDで一括取得
ids = [1, 2, 3]
tasks = await repo.find_by_ids(ids)  # List[Task]

# 空リスト
tasks = await repo.find_by_ids([])  # []

# 存在しないIDは無視される
tasks = await repo.find_by_ids([1, 999, 3])  # ID 999は取得されない

# 重複IDは自動で除外
tasks = await repo.find_by_ids([1, 1, 2])  # IDごとのレコードは1つだけ
```

**ソフトデリート対応**

```python
# 論理削除されたレコードも含める
tasks = await repo.find_by_ids([1, 2, 3], include_deleted=True)

# デフォルト：論理削除を除外
tasks = await repo.find_by_ids([1, 2, 3])  # include_deleted=False
```

**論理削除の詳細** については [SoftDelete ガイド](repository_soft_delete_guide.md) を参照してください。

**注意事項**

- 返却順序は保証されません。必要な場合はアプリケーション側でソート
- 大量のIDを指定する場合、データベースの制限に注意
- connection poolの設定は `repom.config.RepomConfig.engine_kwargs` で調整可能

---

### find() メソッド

```python
from sqlalchemy import and_, or_

# 基本的な検索
tasks = await repo.find()  # 全件

# フィルタ条件付き
filters = [Task.status == 'active']
tasks = await repo.find(filters=filters)

# 複数条件（AND）
filters = [
    Task.status == 'active',
    Task.priority == 'high'
]
tasks = await repo.find(filters=filters)

# OR 条件
filters = [
    or_(
        Task.status == 'active',
        Task.status == 'pending'
    )
]
tasks = await repo.find(filters=filters)
```

### ページネーション

```python
# offset と limit
tasks = await repo.find(offset=0, limit=10)

# 2ページ目（1ページ10件）
tasks = await repo.find(offset=10, limit=10)
```

### ソート

```python
# デフォルト: id 昇順
tasks = await repo.find()

# 降順・昇順指定（簡易）
tasks = await repo.find(order_by='created_at:desc')
tasks = await repo.find(order_by='title:asc')

# SQLAlchemy 式
from sqlalchemy import desc
tasks = await repo.find(order_by=desc(Task.created_at))

# 複数ソート（カスタムリポジトリで実装）
from sqlalchemy import select, desc
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_sorted(self):
        query = select(Task).order_by(
            desc(Task.priority),
            Task.created_at
        )
        result = await self.session.execute(query)
        return result.scalars().all()
```

### ソート可能なカラムの制限

セキュリティのため、ソート可能なカラムは `allowed_order_columns` で制限されています。
この設定と `parse_order_by()` / `set_find_option()` は `QueryBuilderMixin`
（`BaseRepository` / `AsyncBaseRepository` で共通継承）にまとめられており、
同期・非同期の両方で同じロジックが適用されます。

```python
from repom import AsyncBaseRepository

# デフォルトで許可されているカラム
AsyncBaseRepository.allowed_order_columns = [
    'id', 'title', 'created_at', 'updated_at',
    'started_at', 'finished_at', 'executed_at'
]

# カスタムリポジトリで拡張
class TaskRepository(AsyncBaseRepository[Task]):
    allowed_order_columns = AsyncBaseRepository.allowed_order_columns + [
        'priority', 'status'
    ]
```

**同期版**: `AsyncBaseRepository` → `BaseRepository` に変更してください。

**トラブルシューティング**:

```python
# ❌ 許可されていないカラムでソート
tasks = await repo.find(order_by='custom_field:desc')
# → ValueError: Column 'custom_field' is not allowed for sorting

# ✅ allowed_order_columns を拡張
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    allowed_order_columns = AsyncBaseRepository.allowed_order_columns + ['custom_field']
```

### 件数カウント

```python
# 全件数
total = await repo.count()

# 条件付きカウント
filters = [Task.status == 'active']
active_count = await repo.count(filters=filters)
```

---

## Eager Loading（N+1問題の解決）

**関連モデルの効率的な取得**

SQLAlchemy の `options` パラメータを使用して、N+1 問題を解決できます。

**対応メソッド**:
- ✅ `find()` - 複数レコード取得
- ✅ `find_one()` - 単一レコード取得
- ✅ `get_by_id()` - ID で単一レコード取得
- ✅ `get_by()` - カラム条件で取得（単一/複数両対応）

### 基本的な使い方

```python
from sqlalchemy.orm import joinedload, selectinload

# find() で使用
tasks = await repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]
)

# get_by_id() で使用
task = await repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])

# get_by() で使用（単一取得）
task = await repo.get_by('title', 'タスク1', single=True, options=[
    joinedload(Task.user)
])

# get_by() で使用（複数取得）
tasks = await repo.get_by('status', 'active', options=[
    selectinload(Task.comments)
])

# find_one() で使用
task = await repo.find_one(
    filters=[Task.id == 1],
    options=[joinedload(Task.user)]
)
```

### joinedload - 1対1 / 多対1 に最適

```python
from sqlalchemy.orm import joinedload

# 基本的な使い方
tasks = await repo.find(
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

### selectinload - 1対多 / 多対多に最適

```python
from sqlalchemy.orm import selectinload

# コレクション（1対多）を効率的に取得
users = await user_repo.find(
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

### 複数の関連モデルを同時に取得

```python
tasks = await repo.find(
    options=[
        joinedload(Task.user),        # 1対1
        selectinload(Task.tags),      # 1対多
        selectinload(Task.comments)   # 1対多
    ]
)
```

### ネストした関連モデル

```python
# task → user → department
tasks = await repo.find(
    options=[
        joinedload(Task.user).joinedload(User.department)
    ]
)

for task in tasks:
    print(task.user.department.name)  # N+1 なし
```

### デフォルト Eager Loading（default_options）

**NEW in v1.x**: コンストラクタで `default_options` を設定することで、リポジトリのすべての取得メソッドで自動的に eager loading を適用できます。

#### 基本的な使い方

```python
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Task, session)
        # デフォルトで user と comments を eager load
        self.default_options = [
            joinedload(Task.user),
            selectinload(Task.comments)
        ]

# 使用例
repo = TaskRepository(session=async_session)

# options を指定しなくても自動的に eager loading される
tasks = await repo.find()  # user と comments がロード済み
task = await repo.get_by_id(1)  # 同じく自動適用
```

**同期版**: `AsyncSession` → `Session`、`AsyncBaseRepository` → `BaseRepository`、`await` を削除してください。

#### 影響を受けるメソッド

`default_options` は以下のメソッドで自動的に適用されます：

- ✅ `find()` - 複数レコード取得
- ✅ `find_one()` - 単一レコード取得
- ✅ `get_by_id()` - ID で取得
- ✅ `get_by()` - カラム条件で取得

#### options の優先順位

```python
# 1. options=None（デフォルト）: default_options を使用
tasks = await repo.find()  # default_options が適用される

# 2. options=[]（空リスト）: eager loading なし
tasks = await repo.find(options=[])  # default_options をスキップ

# 3. options=[...]（明示指定）: 指定した options を使用
tasks = await repo.find(options=[
    selectinload(Task.tags)  # default_options は無視される
])
```

#### パフォーマンスへの影響

**メリット：N+1 問題の解決**:

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

**デメリット：不要な eager load**:

リレーションを使わない場合でも eager load が発生します。その場合は `options=[]` で無効化できます：

```python
# リレーション不要な場合は明示的にスキップ
task_ids = [task.id for task in repo.find(options=[])]  # 高速
```

#### クラス属性で default_options / default_order_by を設定する

コンストラクタで代入する代わりに、クラス属性でまとめて持つこともできます。`QueryBuilderMixin` がクラス属性を優先して参照するため、継承構造があっても上書きが簡単です。

```python
from sqlalchemy.orm import joinedload
from repom import BaseRepository

class TaskRepository(BaseRepository[Task]):
    # すべての取得メソッドに適用されるデフォルト eager load
    default_options = [joinedload(Task.user)]
    # order_by 未指定時の既定ソート（許可カラムのホワイトリストに含まれる必要あり）
    default_order_by = 'created_at:desc'

# 使い方
repo = TaskRepository(session=db_session)
tasks = repo.find()          # user を eager load 済み & created_at desc でソート
latest = repo.find_one()     # default_order_by が自動適用
raw = repo.find(options=[])  # eager loading だけスキップしたい場合
```

### ベストプラクティス

| パターン | 使用する options | 理由 |
|---------|-----------------|------|
| 1対1 / 多対1 | `joinedload` | 1回のクエリで完了|
| 1対多 / 多対多| `selectinload` | カルテシアン積を避ける |
| 深いネスト| `joinedload().joinedload()` | チェーンで接続|
| 条件付き取得| `contains_eager` | フィルタ付き JOIN |
| リレーションを頻繁に使う| `default_options` で設定| N+1 問題を自動的に回避 |
| リレーションをたまに使う| `default_options` なし| 必要に応じて `options` を指定|

### パフォーマンス比較

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

---

## カスタムリポジトリ

### 基本的なカスタムリポジトリ

```python
from repom import AsyncBaseRepository
from typing import List

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_active(self) -> List[Task]:
        """アクティブなタスクを取得"""
        return await self.get_by('status', 'active')
    
    async def find_by_priority(self, priority: str) -> List[Task]:
        """優先度で検索"""
        return await self.get_by('priority', priority)
    
    async def count_active(self) -> int:
        """アクティブなタスクをカウント"""
        filters = [Task.status == 'active']
        return await self.count(filters=filters)
```

**同期版**: `AsyncBaseRepository` → `BaseRepository`、`async def` → `def`、`await` を削除してください。

### 複雑な検索ロジック

```python
from sqlalchemy import and_, or_, select
from datetime import datetime, timedelta

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_urgent_tasks(self) -> List[Task]:
        """緊急タスク（高優先度 かつ 期限間近）"""
        deadline = datetime.now() + timedelta(days=3)
        
        filters = [
            Task.priority == 'high',
            Task.due_date <= deadline,
            Task.status != 'completed'
        ]
        
        return await self.find(filters=filters, order_by='due_date:asc')
    
    async def find_overdue_tasks(self) -> List[Task]:
        """期限切れタスク"""
        query = select(Task).where(
            and_(
                Task.due_date < datetime.now(),
                Task.status != 'completed'
            )
        ).order_by(Task.due_date)
        
        result = await self.session.execute(query)
        return result.scalars().all()
```

### 関連モデルの操作

```python
from sqlalchemy import select

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_with_user(self, user_id: int) -> List[Task]:
        """特定ユーザーのタスクを取得"""
        return await self.get_by('user_id', user_id)
    
    async def find_by_tags(self, tags: List[str]) -> List[Task]:
        """タグで検索（多対多）"""
        query = select(Task).join(Task.tags).where(
            Tag.name.in_(tags)
        ).distinct()
        
        result = await self.session.execute(query)
        return result.scalars().all()
```

### options を活用したカスタムメソッド

```python
from sqlalchemy.orm import joinedload, selectinload

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_with_user(self, **kwargs):
        """ユーザー情報を含めて取得"""
        return await self.find(
            options=[joinedload(Task.user)],
            **kwargs
        )
    
    async def find_full(self, **kwargs):
        """すべての関連情報を含めて取得"""
        return await self.find(
            options=[
                joinedload(Task.user),
                selectinload(Task.tags),
                selectinload(Task.comments)
            ],
            **kwargs
        )
```

---

## 実装パターン：ビジネスロジックとの統合

```python
from datetime import datetime
from typing import List

class OrderRepository(AsyncBaseRepository[Order]):
    async def create_order(self, user_id: int, items: List[dict]) -> Order:
        """注文作成（ビジネスロジック込み）"""
        # 合計金額を計算
        total = sum(item['price'] * item['quantity'] for item in items)
        
        # 注文作成
        order = Order(
            user_id=user_id,
            status='pending',
            total_amount=total
        )
        
        return await self.save(order)
    
    async def complete_order(self, order_id: int) -> Order:
        """注文完了"""
        order = await self.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status != 'pending':
            raise ValueError(f"Order {order_id} is already {order.status}")
        
        order.status = 'completed'
        order.completed_at = datetime.now()
        
        return await self.save(order)
    
    async def cancel_order(self, order_id: int) -> Order:
        """注文キャンセル"""
        order = await self.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status == 'completed':
            raise ValueError("Cannot cancel completed order")
        
        order.status = 'cancelled'
        order.cancelled_at = datetime.now()
        
        return await self.save(order)
```

**同期版**: `AsyncBaseRepository` → `BaseRepository`、`async def` → `def`、`await` を削除してください。

---

## 次のステップ

- **[基礎編：CRUD操作](base_repository_guide.md)** - リポジトリの基本的な使い方
- **[FastAPI 統合編：FilterParams](repository_filter_params_guide.md)** - FastAPI での検索パラメータ処理

## 関連ドキュメント

- **[auto_import_models ガイド](../features/auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseModelAuto ガイド](../model/base_model_auto_guide.md)**: スキーマ自動生成
- **[BaseModel ソースコード](../../../repom/models/base_model.py)**: BaseModel 実装の詳細
- **[BaseRepository ソースコード](../../../repom/repositories/base_repository.py)**: BaseRepository 実装の詳細

---

**最終更新**: 2026-01-21  
**対象バージョン**: repom v2.0+
