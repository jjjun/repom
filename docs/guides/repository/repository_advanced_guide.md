# Repository 上級ガイド（検索・フィルタ・options�E�E

**目皁E*: 褁E��な検索、パフォーマンス最適化、カスタムリポジトリの実裁E

**対象読老E*: 褁E��な検索機�EめE��フォーマンス最適化が忁E��な開発老E�EAI エージェンチE

**前提**: こ�Eガイド�E非同期コード！EAsyncBaseRepository`�E�を使用してぁE��す。同期版�E�EBaseRepository`�E�も同様に動作しますが、`await` を削除してください、E

**関連ドキュメンチE*:
- [基礎編�E�CRUD操作](base_repository_guide.md) - リポジトリの基本皁E��使ぁE��
- [FastAPI 統合編�E�FilterParams](repository_filter_params_guide.md) - FastAPI での検索パラメータ処琁E
- [非同期版](async_repository_guide.md) - AsyncBaseRepository 固有�E機�E�E�並行�E琁E��ど�E�E

---

## 📚 目次

1. [検索とフィルタリング](#検索とフィルタリング)
2. [Eager Loading�E�E+1問題�E解決�E�](#eager-loadingn1問題�E解決)
3. [カスタムリポジトリ](#カスタムリポジトリ)
4. [実裁E��ターン�E�ビジネスロジチE��統吁E(#実裁E��ターンビジネスロジチE��統吁E

---

## 検索とフィルタリング

### find_by_ids() メソチE�� - 効玁E��な一括取征E

**N+1 問題�E解決に最適**

```python
# N+1 問題を避ける�E�❌ 悪ぁE��！E
for task_id in task_ids:
    task = await repo.get_by_id(task_id)  # N回�Eクエリ�E�E
    # ... 処琁E

# 一括取得で解決�E�✅ 良ぁE��！E
tasks = await repo.find_by_ids(task_ids)  # 1回�Eクエリ
task_dict = {task.id: task for task in tasks}
for task_id in task_ids:
    task = task_dict.get(task_id)
    # ... 処琁E
```

**基本皁E��使ぁE��**

```python
# 褁E��IDで一括取征E
ids = [1, 2, 3]
tasks = await repo.find_by_ids(ids)  # List[Task]

# 空リスチE
tasks = await repo.find_by_ids([])  # []

# 存在しないIDは無視される
tasks = await repo.find_by_ids([1, 999, 3])  # ID 999は取得されなぁE

# 重複IDは自動で除夁E
tasks = await repo.find_by_ids([1, 1, 2])  # IDぁEのレコード�E1つだぁE
```

**ソフトチE��ート対忁E*

```python
# 論理削除されたレコードも含める
tasks = await repo.find_by_ids([1, 2, 3], include_deleted=True)

# チE��ォルト�E論理削除を除夁E
tasks = await repo.find_by_ids([1, 2, 3])  # include_deleted=False
```

**論理削除の詳細** につぁE��は [SoftDelete ガイド](repository_soft_delete_guide.md) を参照してください、E

```python
```

**注意事頁E*

- 返却頁E���E保証されません�E�忁E��な場合�Eアプリケーション側でソート！E
- 大量�EIDを指定する場合、データベ�Eスの制限に注愁E
- connection poolの設定�E `repom.config.RepomConfig.engine_kwargs` で調整可能

---

### find() メソチE��

```python
from sqlalchemy import and_, or_

# 基本皁E��検索
tasks = await repo.find()  # 全件

# フィルタ条件付き
filters = [Task.status == 'active']
tasks = await repo.find(filters=filters)

# 褁E��条件�E�END�E�E
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

### ペ�Eジネ�Eション

```python
# offset と limit
tasks = await repo.find(offset=0, limit=10)

# 2ペ�Eジ目�E�Eペ�Eジ10件�E�E
tasks = await repo.find(offset=10, limit=10)
```

### ソーチE

```python
# チE��ォルチE id 昁E��E
tasks = await repo.find()

# 斁E���E持E��（簡易！E
tasks = await repo.find(order_by='created_at:desc')
tasks = await repo.find(order_by='title:asc')

# SQLAlchemy 弁E
from sqlalchemy import desc
tasks = await repo.find(order_by=desc(Task.created_at))

# 褁E��ソート（カスタムリポジトリで実裁E��E
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

### ソート可能なカラムの制陁E

セキュリチE��のため、ソート可能なカラムは `allowed_order_columns` で制限されてぁE��す、E
こ�E設定と `parse_order_by()` / `set_find_option()` は `QueryBuilderMixin`
�E�EBaseRepository` / `AsyncBaseRepository` で共通継承�E�にまとめられており、E
同期・非同期�E両方で同じロジチE��が適用されます、E

```python
from repom import AsyncBaseRepository

# チE��ォルトで許可されてぁE��カラム
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

**同期牁E*: `AsyncBaseRepository` ↁE`BaseRepository` に変更してください、E

**トラブルシューチE��ング**:

```python
# ❁E許可されてぁE��ぁE��ラムでソーチE
tasks = await repo.find(order_by='custom_field:desc')
# ↁEValueError: Column 'custom_field' is not allowed for sorting

# ✁Eallowed_order_columns を拡張
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    allowed_order_columns = AsyncBaseRepository.allowed_order_columns + ['custom_field']
```

### 件数カウンチE

```python
# 全件数
total = await repo.count()

# 条件付きカウンチE
filters = [Task.status == 'active']
active_count = await repo.count(filters=filters)
```

---

## Eager Loading�E�E+1問題�E解決�E�E

**関連モチE��の効玁E��な取征E*

SQLAlchemy の `options` パラメータを使用して、N+1 問題を解決できます、E

**対応メソチE��**:
- ✁E`find()` - 褁E��レコード取征E
- ✁E`find_one()` - 単一レコード取征E
- ✁E`get_by_id()` - ID で単一レコード取征E
- ✁E`get_by()` - カラム条件で取得（単一/褁E��両対応！E

### 基本皁E��使ぁE��

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

# get_by() で使用�E�単一取得！E
task = await repo.get_by('title', 'タスク1', single=True, options=[
    joinedload(Task.user)
])

# get_by() で使用�E�褁E��取得！E
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

# 基本皁E��使ぁE��
tasks = await repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]  # user めEJOIN で取征E
)

# N+1 なしでアクセス可能
for task in tasks:
    print(task.user.name)  # 追加のクエリなぁE
```

**SQL侁E*:
```sql
SELECT tasks.*, users.*
FROM tasks
LEFT OUTER JOIN users ON users.id = tasks.user_id
WHERE tasks.status = 'active';
```

### selectinload - 1対夁E/ 多対夁Eに最適

```python
from sqlalchemy.orm import selectinload

# コレクション�E�E対多）を効玁E��に取征E
users = await user_repo.find(
    options=[selectinload(User.tasks)]  # 関連するタスクを取征E
)

# N+1 なしでアクセス可能
for user in users:
    for task in user.tasks:  # 追加のクエリなぁE
        print(task.title)
```

**SQL侁E*:
```sql
-- 1. ユーザーを取征E
SELECT * FROM users;

-- 2. 関連するタスクを一括取得！EN句�E�E
SELECT * FROM tasks WHERE user_id IN (1, 2, 3, ...);
```

### 褁E��の関連モチE��を同時に取征E

```python
tasks = await repo.find(
    options=[
        joinedload(Task.user),        # 1対1
        selectinload(Task.tags),      # 1対夁E
        selectinload(Task.comments)   # 1対夁E
    ]
)
```

### ネストした関連モチE��

```python
# task ↁEuser ↁEdepartment
tasks = await repo.find(
    options=[
        joinedload(Task.user).joinedload(User.department)
    ]
)

for task in tasks:
    print(task.user.department.name)  # N+1 なぁE
```

### チE��ォルチEEager Loading�E�Eefault_options�E�E

**NEW in v1.x**: コンストラクタで `default_options` を設定することで、リポジトリのすべての取得メソチE��で自動的に eager loading を適用できます、E

#### 基本皁E��使ぁE��

```python
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Task, session)
        # チE��ォルトで user と comments めEeager load
        self.default_options = [
            joinedload(Task.user),
            selectinload(Task.comments)
        ]

# 使用侁E
repo = TaskRepository(session=async_session)

# options を指定しなくても�E動的に eager loading されめE
tasks = await repo.find()  # user と comments がロード済み
task = await repo.get_by_id(1)  # 同じく�E動適用
```

**同期牁E*: `AsyncSession` ↁE`Session`、`AsyncBaseRepository` ↁE`BaseRepository`、`await` を削除してください、E

#### 影響を受けるメソチE��

`default_options` は以下�EメソチE��で自動的に適用されます！E

- ✁E`find()` - 褁E��レコード取征E
- ✁E`find_one()` - 単一レコード取征E
- ✁E`get_by_id()` - ID で取征E
- ✁E`get_by()` - カラム条件で取征E

#### options の優先頁E��E

```python
# 1. options=None�E�デフォルト）�E default_options を使用
tasks = await repo.find()  # default_options が適用されめE

# 2. options=[] �E�空リスト）�E eager loading なぁE
tasks = await repo.find(options=[])  # default_options をスキチE�E

# 3. options=[...] �E��E示持E��）�E 持E��しぁEoptions を使用
tasks = await repo.find(options=[
    selectinload(Task.tags)  # default_options は無視される
])
```

#### パフォーマンスへの影響

**メリチE���E�E+1 問題�E解決�E�E*:

```python
# Without default_options
tasks = repo.find()  # 1回�Eクエリ
for task in tasks:
    print(task.user.name)  # N回�Eクエリ�E�E+1 問題！E
# 合訁E 1 + N = 101回�Eクエリ�E�E=100の場合！E

# With default_options
class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)
        self.default_options = [joinedload(Task.user)]

tasks = repo.find()  # 2回�Eクエリ�E�Easks と users�E�E
for task in tasks:
    print(task.user.name)  # クエリなぁE
# 合訁E 2回�Eクエリ�E�E=100でも同じ！E
```

**チE��リチE���E�不要な eager load�E�E*:

リレーションを使わなぁE��合でめEeager load が発生します。その場合�E `options=[]` で無効化できます！E

```python
# リレーション不要な場合�E明示皁E��スキチE�E
task_ids = [task.id for task in repo.find(options=[])]  # 高送E
```

#### クラス属性で default_options / default_order_by を設定すめE

コンストラクタで代入する代わりに、クラス属性でまとめて持E��できます。`QueryBuilderMixin` がクラス属性を優先して参�Eするため、継承構造があっても上書きが簡単です、E

```python
from sqlalchemy.orm import joinedload
from repom.repositories import BaseRepository

class TaskRepository(BaseRepository[Task]):
    # すべての取得メソチE��に適用されるデフォルチEeager load
    default_options = [joinedload(Task.user)]
    # order_by 未持E��時の既定ソート（許可カラムのホワイトリストに含まれる忁E��あり！E
    default_order_by = 'created_at:desc'

# 使ぁE��
repo = TaskRepository(session=db_session)
tasks = repo.find()          # user めEeager load 済み & created_at desc でソーチE
latest = repo.find_one()     # default_order_by が�E動適用
raw = repo.find(options=[])  # eager loading だけスキチE�EしたぁE��吁E
```

### ベスト�EラクチE��ス

| パターン | 使用する options | 琁E�� |
|---------|-----------------|------|
| 1対1 / 多対1 | `joinedload` | 1回�Eクエリで完絁E|
| 1対夁E/ 多対夁E| `selectinload` | カルチE��アン積を避ける |
| 深ぁE��スチE| `joinedload().joinedload()` | チェーンで接綁E|
| 条件付き取征E| `contains_eager` | フィルタ付き JOIN |
| リレーションを頻繁に使ぁE| `default_options` で設宁E| N+1 問題を自動的に回避 |
| リレーションをたまに使ぁE| `default_options` なぁE| 忁E��に応じて `options` を指宁E|

### パフォーマンス比輁E

```python
# ❁EN+1 問題！E01回�Eクエリ�E�E
tasks = repo.find()  # 1囁E
for task in tasks:   # 100件
    user = task.user # 100回�Eクエリ

# ✁Ejoinedload�E�E回�Eクエリ�E�E
tasks = repo.find(options=[joinedload(Task.user)])
for task in tasks:
    user = task.user # クエリなぁE

# ✁Eselectinload�E�E回�Eクエリ�E�E
tasks = repo.find(options=[selectinload(Task.tags)])
for task in tasks:
    tags = task.tags # クエリなぁE

# ❁Eget_by_id() で N+1 問顁E
task = repo.get_by_id(1)
user = task.user      # 追加クエリ発甁E
comments = task.comments  # 追加クエリ発甁E

# ✁Eget_by_id() + options で解決
task = repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])
user = task.user      # クエリなぁE
comments = task.comments  # クエリなぁE
```

---

## カスタムリポジトリ

### 基本皁E��カスタムリポジトリ

```python
from repom.repositories import AsyncBaseRepository
from typing import List

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_active(self) -> List[Task]:
        """アクチE��ブなタスクを取征E""
        return await self.get_by('status', 'active')
    
    async def find_by_priority(self, priority: str) -> List[Task]:
        """優先度で検索"""
        return await self.get_by('priority', priority)
    
    async def count_active(self) -> int:
        """アクチE��ブなタスクをカウンチE""
        filters = [Task.status == 'active']
        return await self.count(filters=filters)
```

**同期牁E*: `AsyncBaseRepository` ↁE`BaseRepository`、`async def` ↁE`def`、`await` を削除してください、E

### 褁E��な検索ロジチE��

```python
from sqlalchemy import and_, or_, select
from datetime import datetime, timedelta

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_urgent_tasks(self) -> List[Task]:
        """緊急タスク�E�高優先度 かつ 期限間近！E""
        deadline = datetime.now() + timedelta(days=3)
        
        filters = [
            Task.priority == 'high',
            Task.due_date <= deadline,
            Task.status != 'completed'
        ]
        
        return await self.find(filters=filters, order_by='due_date:asc')
    
    async def find_overdue_tasks(self) -> List[Task]:
        """期限刁E��タスク"""
        query = select(Task).where(
            and_(
                Task.due_date < datetime.now(),
                Task.status != 'completed'
            )
        ).order_by(Task.due_date)
        
        result = await self.session.execute(query)
        return result.scalars().all()
```

### 関連モチE��の操佁E

```python
from sqlalchemy import select

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_with_user(self, user_id: int) -> List[Task]:
        """特定ユーザーのタスクを取征E""
        return await self.get_by('user_id', user_id)
    
    async def find_by_tags(self, tags: List[str]) -> List[Task]:
        """タグで検索�E�多対多！E""
        query = select(Task).join(Task.tags).where(
            Tag.name.in_(tags)
        ).distinct()
        
        result = await self.session.execute(query)
        return result.scalars().all()
```

### options を活用したカスタムメソチE��

```python
from sqlalchemy.orm import joinedload, selectinload

class TaskRepository(AsyncBaseRepository[Task]):
    async def find_with_user(self, **kwargs):
        """ユーザー惁E��を含めて取征E""
        return await self.find(
            options=[joinedload(Task.user)],
            **kwargs
        )
    
    async def find_full(self, **kwargs):
        """すべての関連惁E��を含めて取征E""
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

## 実裁E��ターン�E�ビジネスロジチE��統吁E

```python
from datetime import datetime
from typing import List

class OrderRepository(AsyncBaseRepository[Order]):
    async def create_order(self, user_id: int, items: List[dict]) -> Order:
        """注斁E��作�E�E�ビジネスロジチE���E�E""
        # 合計��額を計箁E
        total = sum(item['price'] * item['quantity'] for item in items)
        
        # 注斁E��作�E
        order = Order(
            user_id=user_id,
            status='pending',
            total_amount=total
        )
        
        return await self.save(order)
    
    async def complete_order(self, order_id: int) -> Order:
        """注斁E��完亁E""
        order = await self.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status != 'pending':
            raise ValueError(f"Order {order_id} is already {order.status}")
        
        order.status = 'completed'
        order.completed_at = datetime.now()
        
        return await self.save(order)
    
    async def cancel_order(self, order_id: int) -> Order:
        """注斁E��キャンセル"""
        order = await self.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if order.status == 'completed':
            raise ValueError("Cannot cancel completed order")
        
        order.status = 'cancelled'
        order.cancelled_at = datetime.now()
        
        return await self.save(order)
```

**同期牁E*: `AsyncBaseRepository` ↁE`BaseRepository`、`async def` ↁE`def`、`await` を削除してください、E

---

## 次のスチE��チE

- **[基礎編�E�CRUD操作](base_repository_guide.md)** - リポジトリの基本皁E��使ぁE��
- **[FastAPI 統合編�E�FilterParams](repository_filter_params_guide.md)** - FastAPI での検索パラメータ処琁E

## 関連ドキュメンチE

- **[auto_import_models ガイド](../core/auto_import_models_guide.md)**: モチE��の自動インポ�EチE
- **[BaseModelAuto ガイド](../features/base_model_auto_guide.md)**: スキーマ�E動生戁E
- **[BaseRepository ソースコード](../../../repom/repositories/base_repository.py)**: 実裁E�E詳細

---

**最終更新**: 2025-12-28  
**対象バ�Eジョン**: repom v2.0+
