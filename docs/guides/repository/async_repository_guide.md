# AsyncBaseRepository ガイチE

**目皁E*: repom の `AsyncBaseRepository` による非同期データアクセスパターンを理解する

**対象読老E*: FastAPI など非同期フレームワークで repom を使ぁE��発老E�EAI エージェンチE

---

## 📚 目次

1. [はじめに](#はじめに)
2. [基本皁E��使ぁE��](#基本皁E��使ぁE��)
3. [FastAPI 統吁E(#fastapi-統吁E
4. [非同朁ECRUD 操作](#非同朁Ecrud-操佁E
5. [検索とフィルタリング](#検索とフィルタリング)
6. [Eager Loading�E�E+1 問題�E解決�E�](#eager-loading)
7. [並行�E琁E��ターン](#並行�E琁E��ターン)
8. [ベスト�EラクチE��ス](#ベスト�EラクチE��ス)

---

## はじめに

### AsyncBaseRepository とは

`AsyncBaseRepository` は `BaseRepository` の完�E非同期版です。すべてのメソチE��ぁE`async def` で定義され、`AsyncSession` を使用してチE�Eタベ�Eス操作を行います、E

### BaseRepository との違い

| 頁E�� | BaseRepository | AsyncBaseRepository |
|------|----------------|---------------------|
| セチE��ョン垁E| `Session` | `AsyncSession` |
| メソチE�� | 同期�E�通常の関数�E�E| 非同期！Easync def`�E�E|
| 呼び出ぁE| `repo.find()` | `await repo.find()` |
| 用送E| 同期アプリケーション | FastAPI, 非同期アプリ |

### ぁE��使ぁE��

✁E**AsyncBaseRepository を使ぁE��き場吁E*:
- FastAPI などの非同期フレームワーク
- 高並行性が求められるアプリケーション
- I/O バウンドな処琁E��多い場吁E
- asyncio.gather で並行�E琁E��たい場吁E

❁E**BaseRepository で十�Eな場吁E*:
- スクリプトめE��チE��処琁E
- 単純な CRUD 操作�Eみ
- 並行性が不要な場吁E

---

## 基本皁E��使ぁE��

### リポジトリの作�E

```python
from repom import AsyncBaseRepository
from repom.database import get_async_db_session
from your_project.models import Task
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# FastAPI Depends パターンで使用�E�推奨�E�E
async def get_task(task_id: int, session: AsyncSession = Depends(get_async_db_session)):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    return task
```

### 主要メソチE��一覧

すべてのメソチE��は `async def` で、`await` が忁E��です、E

| メソチE�� | 用送E| 戻り値 |
|---------|------|--------|
| `await get_by_id(id)` | ID で取征E| `Optional[T]` |
| `await get_by(column, value)` | カラムで検索 | `List[T]` |
| `await get_all()` | 全件取征E| `List[T]` |
| `await find(filters, **options)` | 条件検索 | `List[T]` |
| `await find_one(filters)` | 単一検索 | `Optional[T]` |
| `await count(filters)` | 件数カウンチE| `int` |
| `await save(instance)` | 保孁E| `T` |
| `await saves(instances)` | 一括保孁E| `None` |
| `await remove(instance)` | 削除 | `None` |
| `await soft_delete(id)` | 論理削除 | `bool` |
| `await restore(id)` | 復允E| `bool` |
| `await find_deleted()` | 削除済み取征E| `List[T]` |

---

## FastAPI 統吁E

### 基本皁E��統合パターン

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session
from repom import AsyncBaseRepository
from your_project.models import Task

app = FastAPI()

@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

### カスタムリポジトリを使ぁE��況E

```python
from typing import List
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    """タスク専用リポジトリ"""
    
    async def find_active_tasks(self) -> List[Task]:
        """アクチE��ブなタスクのみ取征E""
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_by_user(self, user_id: int) -> List[Task]:
        """特定ユーザーのタスクを取征E""
        return await self.find(filters=[Task.user_id == user_id])

# FastAPI で使用
@app.get("/tasks/active")
async def get_active_tasks(session: AsyncSession = Depends(get_async_db_session)):
    repo = TaskRepository(Task, session)
    return await repo.find_active_tasks()
```

### リポジトリめEDepends で注入

```python
from typing import Annotated

def get_task_repo(session: AsyncSession = Depends(get_async_db_session)):
    return TaskRepository(Task, session)

TaskRepoDep = Annotated[TaskRepository, Depends(get_task_repo)]

@app.get("/tasks")
async def list_tasks(repo: TaskRepoDep):
    return await repo.find()

@app.get("/tasks/{task_id}")
async def get_task(task_id: int, repo: TaskRepoDep):
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404)
    return task
```

---

## 非同朁ECRUD 操佁E

### Create�E�作�E�E�E

```python
# FastAPI エンド�Eイントでの使用侁E
@app.post("/tasks")
async def create_task(
    task_data: dict,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    
    # 1件保孁E
    task = Task(title=task_data["title"], status="active")
    saved_task = await repo.save(task)
    
    # 辞書から保孁E
    task = await repo.dict_save({"title": "タスク2", "status": "pending"})
    
    # 褁E��保孁E
    tasks = [Task(title=f"タスク{i}") for i in range(3)]
    await repo.saves(tasks)
    
    # 辞書リストから保孁E
    data_list = [{"title": f"タスク{i}"} for i in range(3)]
    await repo.dict_saves(data_list)
    
    return saved_task
```

### Read�E�取得！E

```python
# FastAPI エンド�Eイントでの使用侁E
@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    
    # ID で取征E
    task = await repo.get_by_id(task_id)
    
    # カラムで検索�E�褁E��件�E�E
    active_tasks = await repo.get_by('status', 'active')
    
    # 単一取得！Eingle=True�E�E
        task = await repo.get_by('title', 'タスク1', single=True)
        
        # 全件取征E
        all_tasks = await repo.get_all()
```

### Update�E�更新�E�E

```python
async def update_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # インスタンスを取得して更新
        task = await repo.get_by_id(task_id)
        if task:
            task.status = 'completed'
            await repo.save(task)
        
        # また�E BaseModel の update_from_dict を使用
        task.update_from_dict({"status": "completed"})
        await repo.save(task)
```

### Delete�E�削除�E�E

```python
async def delete_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 物琁E��除�E�完�E削除�E�E
        task = await repo.get_by_id(task_id)
        if task:
            await repo.remove(task)
```

---

## 検索とフィルタリング

非同期版でも検索・フィルタリング機�Eは同期版と同じです。詳細は **[Repository 上級ガイド](repository_advanced_guide.md)** を参照してください、E

### クイチE��リファレンス

```python
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    
    # 基本検索
    tasks = await repo.find(filters=[Task.status == 'active'])
    
    # ペ�Eジネ�Eション
    tasks = await repo.find(offset=0, limit=20, order_by='created_at:desc')
    
    # カウンチE
    count = await repo.count(filters=[Task.status == 'active'])
```

詳細なフィルタリングパターン�E�END/OR、LIKE、IN句など�E��E [Repository 上級ガイド](repository_advanced_guide.md#検索とフィルタリング) を参照してください、E

---

## Eager Loading�E�E+1 問題�E解決�E�E

非同期版でめEEager Loading の仕絁E��は同期版と同じです。詳細は **[Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題�E解決)** を参照してください、E

### クイチE��リファレンス

```python
from sqlalchemy.orm import joinedload, selectinload

# find() で使用
tasks = await repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]
)

# get_by_id() で使用�E�EEW!�E�E
task = await repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])

# get_by() で使用�E�EEW!�E�E
task = await repo.get_by('title', 'タスク1', single=True, options=[
    joinedload(Task.user)
])

# find_one() で使用�E�EEW!�E�E
task = await repo.find_one(
    filters=[Task.id == 1],
    options=[joinedload(Task.user)]
)
```

詳細な使ぁE��、パフォーマンス比輁E���Eスト�EラクチE��スは [Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題�E解決) を参照してください、E

### default_options による自動適用

```python
class TaskRepository(AsyncBaseRepository[Task]):
    # クラス属性で持E��（推奨�E�E
    default_options = [
        joinedload(Task.user),
        selectinload(Task.comments)
    ]

# すべての取得メソチE��で自動適用
repo = TaskRepository(session=session)
tasks = await repo.find()  # user と comments が�E動ローチE
task = await repo.get_by_id(1)  # 同じく�E動適用
```

詳細は [Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題�E解決) を参照してください、E

---

## カスタムリポジトリ

ビジネスロジチE��を含むカスタムリポジトリの作�E方法�E **[Repository 上級ガイド](repository_advanced_guide.md#カスタムリポジトリ)** を参照してください、E

### クイチE��リファレンス

```python
class TaskRepository(AsyncBaseRepository[Task]):
    async def find_active(self) -> List[Task]:
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_overdue(self) -> List[Task]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return await self.find(
            filters=[
                Task.status != 'completed',
                Task.due_date < now
            ]
        )
```

褁E��な検索ロジチE��、E��連モチE��操作、ビジネスロジチE��統合�E詳細は [Repository 上級ガイド](repository_advanced_guide.md#カスタムリポジトリ) を参照してください、E

---

## 論理削除�E�EoftDelete�E�E

論理削除機�Eの使ぁE��は **[SoftDelete ガイド](repository_soft_delete_guide.md)** を参照してください。非同期版�E実裁E��も含まれてぁE��す、E

### クイチE��リファレンス

```python
# 論理削除
await repo.soft_delete(task_id)

# 復允E
await repo.restore(task_id)

# 削除済みを含めて検索
tasks = await repo.find(include_deleted=True)

# 削除済みのみ取征E
deleted_tasks = await repo.find_deleted()
```

詳細は [SoftDelete ガイド](repository_soft_delete_guide.md) を参照してください、E

---

## 非同期特有�E機�E

以下�Eセクションは AsyncBaseRepository に特有�E機�Eです、E

---

## 並行�E琁E��ターン

### asyncio.gather による並行実衁E

```python
import asyncio

async def fetch_multiple_resources():
    async with get_async_db_session() as session:
        task_repo = AsyncBaseRepository(Task, session)
        user_repo = AsyncBaseRepository(User, session)
        project_repo = AsyncBaseRepository(Project, session)
        
        # 3つのクエリを並行実衁E
        tasks, users, projects = await asyncio.gather(
            task_repo.find(filters=[Task.status == 'active']),
            user_repo.get_all(),
            project_repo.find(limit=10)
        )
        
        return {
            "tasks": tasks,
            "users": users,
            "projects": projects
        }
```
):
    repo = TaskRepository(session=session)
    task = await repo.get_by_id(task_id)  # default_options 適用
    if not task:
        raise HTTPException(status_code=404)
    return task
```

### パフォーマンスへの影響

**メリチE���E�E+1 問題�E解決�E�E*:

```python
# Without default_options
tasks = await repo.find()  # 1回�Eクエリ
for task in tasks:
    print(task.user.name)  # N回�Eクエリ�E�E+1 問題！E
# 合訁E 1 + N = 101回�Eクエリ�E�E=100の場合！E

# With default_options
class TaskRepository(AsyncBaseRepository[Task]):
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
        self.default_options = [joinedload(Task.user)]

tasks = await repo.find()  # 2回�Eクエリ�E�Easks と users�E�E
for task in tasks:
    print(task.user.name)  # クエリなぁE
# 合訁E 2回�Eクエリ�E�E=100でも同じ！E
```

**チE��リチE���E�不要な eager load�E�E*:

リレーションを使わなぁE��合でめEeager load が発生します。その場合�E `options=[]` で無効化！E

```python
# リレーション不要な場合�E明示皁E��スキチE�E
task_ids = [task.id for task in await repo.find(options=[])]  # 高送E
```

### ベスト�EラクチE��ス

| 状況E| 推奨設宁E| 琁E�� |
|------|---------|------|
| リレーションを頻繁に使ぁE| `default_options` で設宁E| N+1 問題を自動的に回避 |
| リレーションをたまに使ぁE| `default_options` なぁE| 忁E��に応じて `options` を指宁E|
| パフォーマンスが重要E| ケースバイケースで `options` を指宁E| 柔軟な最適匁E|

---

### パフォーマンス比輁E

| 方況E| クエリ数 | パフォーマンス |
|-----|---------|--------------|
| Lazy loading | N+1 囁E| ❁E遁E�� |
| joinedload | 1回！EOIN�E�E| ✁E速い |
| selectinload | 2回！EN�E�E| ✁E速い |

**推奨**:
- 多対一�E�ETask.user`�E�E `joinedload`
- 一対多！EProject.tasks`�E�E `selectinload`

---

## 並行�E琁E��ターン

### asyncio.gather による並行実衁E

```python
import asyncio

async def fetch_multiple_resources():
    async with get_async_db_session() as session:
        task_repo = AsyncBaseRepository(Task, session)
        user_repo = AsyncBaseRepository(User, session)
        project_repo = AsyncBaseRepository(Project, session)
        
        # 3つのクエリを並行実衁E
        tasks, users, projects = await asyncio.gather(
            task_repo.find(filters=[Task.status == 'active']),
            user_repo.get_all(),
            project_repo.find(limit=10)
        )
        
        return {
            "tasks": tasks,
            "users": users,
            "projects": projects
        }
```

### FastAPI での並行�E琁E

```python
@app.get("/dashboard")
async def get_dashboard(session: AsyncSession = Depends(get_async_db_session)):
    task_repo = AsyncBaseRepository(Task, session)
    user_repo = AsyncBaseRepository(User, session)
    
    # 褁E��のカウントを並行実衁E
    total_tasks, active_tasks, total_users = await asyncio.gather(
        task_repo.count(),
        task_repo.count(filters=[Task.status == 'active']),
        user_repo.count()
    )
    
    return {
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "total_users": total_users
    }
```

### エラーハンドリング付き並行�E琁E

```python
async def fetch_with_fallback():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        try:
            results = await asyncio.gather(
                repo.get_by_id(1),
                repo.get_by_id(2),
                repo.get_by_id(3),
                return_exceptions=True  # エラーを例外として返す
            )
            
            # 成功したも�Eだけフィルタ
            valid_results = [r for r in results if not isinstance(r, Exception)]
            return valid_results
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
            return []
```

### バッチ�E琁E��ターン

```python
async def process_tasks_in_batches(task_ids: List[int], batch_size: int = 10):
    """大量�EタスクをバチE��処琁E""
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # バッチに刁E��
        for i in range(0, len(task_ids), batch_size):
            batch_ids = task_ids[i:i + batch_size]
            
            # find_by_ids で一括取征E
            tasks = await repo.find_by_ids(batch_ids)
            
            # 処琁E
            for task in tasks:
                task.status = 'processed'
            
            await repo.saves(tasks)
            
            # 少し征E��（負荷軽減！E
            await asyncio.sleep(0.1)
```

---

## ベスト�EラクチE��ス

### ✁EDO: セチE��ョン管琁E

```python
# Good: コンチE��スト�Eネ�Eジャーで自動管琁E
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
    # session は自動的にクローズされめE

# Good: FastAPI の Depends で注入
@app.get("/tasks")
async def list_tasks(session: AsyncSession = Depends(get_async_db_session)):
    repo = AsyncBaseRepository(Task, session)
    return await repo.find()
```

```python
# Bad: セチE��ョンを手動管琁E��クローズ忘れのリスク�E�E
session = AsyncSession(async_engine)
repo = AsyncBaseRepository(Task, session)
task = await repo.get_by_id(1)
await session.close()  # 忘れる可能性
```

### ✁EDO: Eager Loading の使用

```python
# Good: N+1 問題を回避
tasks = await repo.find(
    options=[joinedload(Task.user)]
)

# Bad: Lazy loading�E�E+1 問題発生！E
tasks = await repo.find()
for task in tasks:
    print(task.user.name)  # 吁E��スクで個別クエリ
```

### ✁EDO: 並行�E琁E�E活用

```python
# Good: 独立したクエリは並行実衁E
tasks, users = await asyncio.gather(
    task_repo.find(),
    user_repo.find()
)

# Bad: 頁E��実行（遅ぁE��E
tasks = await task_repo.find()
users = await user_repo.find()
```

### ✁EDO: エラーハンドリング

```python
# Good: 適刁E��エラーハンドリング
try:
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await repo.save(task)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    raise HTTPException(status_code=500, detail="Database error")
```

### ✁EDO: カスタムリポジトリの作�E

```python
# Good: ビジネスロジチE��をリポジトリに雁E��E
class TaskRepository(AsyncBaseRepository[Task]):
    async def find_active_tasks(self) -> List[Task]:
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_overdue_tasks(self) -> List[Task]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return await self.find(
            filters=[
                Task.status != 'completed',
                Task.due_date < now
            ]
        )
```

### ❁EDON'T: リポジトリ冁E��の並行�E琁E

```python
# Bad: リポジトリメソチE��冁E�� asyncio.gather
class TaskRepository(AsyncBaseRepository[Task]):
    async def get_tasks_and_users(self):
        # これはめE��なぁE- 責務が不�E確
        return await asyncio.gather(
            self.find(),
            user_repo.find()  # 他�Eリポジトリに依孁E
        )

# Good: エンド�Eイントで並行�E琁E
@app.get("/data")
async def get_data(session: AsyncSession = Depends(get_async_db_session)):
    task_repo = TaskRepository(Task, session)
    user_repo = UserRepository(User, session)
    
    tasks, users = await asyncio.gather(
        task_repo.find(),
        user_repo.find()
    )
    return {"tasks": tasks, "users": users}
```

### ❁EDON'T: 過度な eager loading

```python
# Bad: 不要な関連まで取征E
tasks = await repo.find(
    options=[
        joinedload(Task.user).joinedload(User.profile),
        selectinload(Task.comments).joinedload(Comment.author),
        joinedload(Task.category).joinedload(Category.parent)
    ]
)

# Good: 忁E��なも�Eだけ取征E
tasks = await repo.find(
    options=[joinedload(Task.user)]
)
```

### ✁EDO: トランザクション管琁E

```python
# Good: 褁E��操作をトランザクションでまとめる
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    
    try:
        task1 = await repo.save(Task(title="Task 1"))
        task2 = await repo.save(Task(title="Task 2"))
        # commit は session close 時に自動実衁E
    except Exception:
        # rollback は自動実衁E
        raise
```

---

## 同期版との比輁E

### コード比輁E

**同期牁E(BaseRepository)**:
```python
from repom import BaseRepository
from repom.db import db_session

with db_session() as session:
    repo = BaseRepository(Task, session)
    task = repo.get_by_id(1)
    tasks = repo.find(filters=[Task.status == 'active'])
```

**非同期版 (AsyncBaseRepository)**:
```python
from repom import AsyncBaseRepository
from repom.database import get_async_db_session

async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
    tasks = await repo.find(filters=[Task.status == 'active'])
```

### 主な変更点

1. `async with` でセチE��ョン取征E
2. すべてのリポジトリメソチE��に `await` が忁E��E
3. 並行�E琁E�E `asyncio.gather` で実現

---

## まとめE

### AsyncBaseRepository の特徴

- **FastAPI など非同期フレームワークで使用**
- すべてのメソチE��は `async def` で `await` が忁E��E
- **並行�E琁E*: `asyncio.gather` で褁E��クエリを並行実衁E
- **セチE��ョン管琁E*: `async with` また�E FastAPI の `Depends` で管琁E

### 機�E別ガイチE

| 機�E | ガイチE| 概要E|
|------|--------|------|
| 基本皁E�� CRUD | [BaseRepository ガイド](base_repository_guide.md) | 取得�E作�E・更新・削除 |
| 検索・フィルタリング | [Repository 上級ガイド](repository_advanced_guide.md#検索とフィルタリング) | find(), ペ�Eジング、ソーチE|
| Eager Loading | [Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題�E解決) | N+1 問題�E解決、default_options |
| カスタムリポジトリ | [Repository 上級ガイド](repository_advanced_guide.md#カスタムリポジトリ) | ビジネスロジチE��の統吁E|
| 論理削除 | [SoftDelete ガイド](repository_soft_delete_guide.md) | soft_delete, restore |
| FastAPI 統吁E| [FilterParams ガイド](repository_filter_params_guide.md) | クエリパラメータの型安�E処琁E|
| チE��チE| [Testing ガイド](../testing/testing_guide.md) | 非同期テスト�Eベスト�EラクチE��ス |

### 非同期版の利点

✁E**高並行性**: 褁E��のクエリを並行実行できる  
✁E**I/O効玁E*: チE�Eタベ�Eス征E��中に他�E処琁E��実衁E 
✁E**FastAPI統吁E*: Depends パターンでシームレスに統吁E 
✁E**スケーラビリチE��**: 多数の同時リクエストを効玁E��に処琁E

### 次のスチE��チE

1. **基礎を学ぶ**: [BaseRepository ガイド](base_repository_guide.md) で CRUD 操作を琁E��
2. **高度な検索**: [Repository 上級ガイド](repository_advanced_guide.md) で検索パターンを学翁E
3. **FastAPI統吁E*: [FilterParams ガイド](repository_filter_params_guide.md) で実践皁E��統合を実裁E
4. **並行�E琁E*: こ�Eガイド�E「並行�E琁E��ターン」を活用

---

**最終更新**: 2025-12-28  
**対象バ�Eジョン**: repom v2.0+
