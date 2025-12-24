# AsyncBaseRepository ガイド

**目的**: repom の `AsyncBaseRepository` による非同期データアクセスパターンを理解する

**対象読者**: FastAPI など非同期フレームワークで repom を使う開発者・AI エージェント

---

## 📚 目次

1. [はじめに](#はじめに)
2. [基本的な使い方](#基本的な使い方)
3. [FastAPI 統合](#fastapi-統合)
4. [非同期 CRUD 操作](#非同期-crud-操作)
5. [検索とフィルタリング](#検索とフィルタリング)
6. [Eager Loading（N+1 問題の解決）](#eager-loading)
7. [並行処理パターン](#並行処理パターン)
8. [論理削除（SoftDelete）](#論理削除)
9. [ベストプラクティス](#ベストプラクティス)

---

## はじめに

### AsyncBaseRepository とは

`AsyncBaseRepository` は `BaseRepository` の完全非同期版です。すべてのメソッドが `async def` で定義され、`AsyncSession` を使用してデータベース操作を行います。

### BaseRepository との違い

| 項目 | BaseRepository | AsyncBaseRepository |
|------|----------------|---------------------|
| セッション型 | `Session` | `AsyncSession` |
| メソッド | 同期（通常の関数） | 非同期（`async def`） |
| 呼び出し | `repo.find()` | `await repo.find()` |
| 用途 | 同期アプリケーション | FastAPI, 非同期アプリ |

### いつ使うか

✅ **AsyncBaseRepository を使うべき場合**:
- FastAPI などの非同期フレームワーク
- 高並行性が求められるアプリケーション
- I/O バウンドな処理が多い場合
- asyncio.gather で並行処理したい場合

❌ **BaseRepository で十分な場合**:
- スクリプトやバッチ処理
- 単純な CRUD 操作のみ
- 並行性が不要な場合

---

## 基本的な使い方

### リポジトリの作成

```python
from repom.async_base_repository import AsyncBaseRepository
from repom.async_session import get_async_db_session
from your_project.models import Task

# 非同期コンテキストマネージャーで使用
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
```

### 主要メソッド一覧

すべてのメソッドは `async def` で、`await` が必要です。

| メソッド | 用途 | 戻り値 |
|---------|------|--------|
| `await get_by_id(id)` | ID で取得 | `Optional[T]` |
| `await get_by(column, value)` | カラムで検索 | `List[T]` |
| `await get_all()` | 全件取得 | `List[T]` |
| `await find(filters, **options)` | 条件検索 | `List[T]` |
| `await find_one(filters)` | 単一検索 | `Optional[T]` |
| `await count(filters)` | 件数カウント | `int` |
| `await save(instance)` | 保存 | `T` |
| `await saves(instances)` | 一括保存 | `None` |
| `await remove(instance)` | 削除 | `None` |
| `await soft_delete(id)` | 論理削除 | `bool` |
| `await restore(id)` | 復元 | `bool` |
| `await find_deleted()` | 削除済み取得 | `List[T]` |

---

## FastAPI 統合

### 基本的な統合パターン

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.async_session import get_async_db_session
from repom.async_base_repository import AsyncBaseRepository
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

### カスタムリポジトリを使う方法

```python
from typing import List
from repom.async_base_repository import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    """タスク専用リポジトリ"""
    
    async def find_active_tasks(self) -> List[Task]:
        """アクティブなタスクのみ取得"""
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_by_user(self, user_id: int) -> List[Task]:
        """特定ユーザーのタスクを取得"""
        return await self.find(filters=[Task.user_id == user_id])

# FastAPI で使用
@app.get("/tasks/active")
async def get_active_tasks(session: AsyncSession = Depends(get_async_db_session)):
    repo = TaskRepository(Task, session)
    return await repo.find_active_tasks()
```

### リポジトリを Depends で注入

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

## 非同期 CRUD 操作

### Create（作成）

```python
async def create_tasks():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 1件保存
        task = Task(title="新しいタスク", status="active")
        saved_task = await repo.save(task)
        
        # 辞書から保存
        task = await repo.dict_save({"title": "タスク2", "status": "pending"})
        
        # 複数保存
        tasks = [Task(title=f"タスク{i}") for i in range(3)]
        await repo.saves(tasks)
        
        # 辞書リストから保存
        data_list = [{"title": f"タスク{i}"} for i in range(3)]
        await repo.dict_saves(data_list)
```

### Read（取得）

```python
async def read_tasks():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # ID で取得
        task = await repo.get_by_id(1)
        
        # カラムで検索（複数件）
        active_tasks = await repo.get_by('status', 'active')
        
        # 単一取得（single=True）
        task = await repo.get_by('title', 'タスク1', single=True)
        
        # 全件取得
        all_tasks = await repo.get_all()
```

### Update（更新）

```python
async def update_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # インスタンスを取得して更新
        task = await repo.get_by_id(task_id)
        if task:
            task.status = 'completed'
            await repo.save(task)
        
        # または BaseModel の update_from_dict を使用
        task.update_from_dict({"status": "completed"})
        await repo.save(task)
```

### Delete（削除）

```python
async def delete_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 物理削除
        task = await repo.get_by_id(task_id)
        if task:
            await repo.remove(task)
        
        # または論理削除（SoftDelete）
        success = await repo.soft_delete(task_id)
```

---

## 検索とフィルタリング

### 基本的な検索

```python
async def search_tasks():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # フィルタなし（全件）
        all_tasks = await repo.find()
        
        # 単一条件
        tasks = await repo.find(filters=[Task.status == 'active'])
        
        # 複数条件（AND）
        from sqlalchemy import and_
        tasks = await repo.find(
            filters=[
                Task.status == 'active',
                Task.priority == 'high'
            ]
        )
```

### ページネーション

```python
# offset と limit
tasks = await repo.find(
    offset=0,
    limit=20,
    order_by='created_at:desc'
)

# ページング関数
async def get_paginated_tasks(page: int = 1, per_page: int = 20):
    offset = (page - 1) * per_page
    tasks = await repo.find(offset=offset, limit=per_page)
    total = await repo.count()
    return {
        "items": tasks,
        "total": total,
        "page": page,
        "per_page": per_page
    }
```

### ソート（order_by）

```python
# 文字列指定
tasks = await repo.find(order_by='created_at:desc')
tasks = await repo.find(order_by='priority:asc')

# SQLAlchemy 式
from sqlalchemy import desc
tasks = await repo.find(order_by=desc(Task.created_at))
```

### カウント

```python
# 全件カウント
total = await repo.count()

# 条件付きカウント
active_count = await repo.count(filters=[Task.status == 'active'])

# 複数条件
high_priority_count = await repo.count(
    filters=[
        Task.status == 'active',
        Task.priority == 'high'
    ]
)
```

---

## Eager Loading

### N+1 問題の解決

AsyncBaseRepository は `options` パラメータをサポートし、SQLAlchemy の `joinedload` や `selectinload` を使って N+1 問題を解決できます。

**対応メソッド**:
- ✅ `await find()` - 複数レコード取得
- ✅ `await find_one()` - 単一レコード取得
- ✅ `await get_by_id()` - ID で単一レコード取得
- ✅ `await get_by()` - カラム条件で取得（単一/複数両対応）

### 基本的な使い方

```python
from sqlalchemy.orm import joinedload, selectinload

# find() で使用
tasks = await repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]
)

# get_by_id() で使用（NEW!）
task = await repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])

# get_by() で使用（NEW!）
task = await repo.get_by('title', 'タスク1', single=True, options=[
    joinedload(Task.user)
])

# find_one() で使用（NEW!）
task = await repo.find_one(
    filters=[Task.id == 1],
    options=[joinedload(Task.user)]
)
```

### joinedload（多対一関係）

```python
from sqlalchemy.orm import joinedload

async def get_tasks_with_user():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # Task と関連する User を一度に取得
        tasks = await repo.find(
            options=[joinedload(Task.user)]
        )
        
        # N+1 なしで user にアクセス可能
        for task in tasks:
            print(f"{task.title} by {task.user.name}")
```

### selectinload（一対多関係）

```python
from sqlalchemy.orm import selectinload

async def get_projects_with_tasks():
    repo = AsyncBaseRepository(Project, session)
    
    # Project と関連する Tasks を一度に取得
    projects = await repo.find(
        options=[selectinload(Project.tasks)]
    )
    
    # N+1 なしで tasks にアクセス可能
    for project in projects:
        print(f"{project.name}: {len(project.tasks)} tasks")
```

### 複数の options を組み合わせ

```python
# 複数の関連モデルを同時に eager load
tasks = await repo.find(
    options=[
        joinedload(Task.user),
        selectinload(Task.comments),
        joinedload(Task.category)
    ]
)
```

### ネストした eager loading

```python
from sqlalchemy.orm import joinedload

# Comment → Task → User とネストして取得
comments = await comment_repo.find(
    options=[
        joinedload(Comment.task).joinedload(Task.user)
    ]
)
```

### options とフィルタの組み合わせ

```python
# フィルタ + eager loading
tasks = await repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)],
    order_by='created_at:desc',
    limit=10
)
```

### パフォーマンス比較

| 方法 | クエリ数 | パフォーマンス |
|-----|---------|--------------|
| Lazy loading | N+1 回 | ❌ 遅い |
| joinedload | 1回（JOIN） | ✅ 速い |
| selectinload | 2回（IN） | ✅ 速い |

**推奨**:
- 多対一（`Task.user`）: `joinedload`
- 一対多（`Project.tasks`）: `selectinload`

---

## 並行処理パターン

### asyncio.gather による並行実行

```python
import asyncio

async def fetch_multiple_resources():
    async with get_async_db_session() as session:
        task_repo = AsyncBaseRepository(Task, session)
        user_repo = AsyncBaseRepository(User, session)
        project_repo = AsyncBaseRepository(Project, session)
        
        # 3つのクエリを並行実行
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

### FastAPI での並行処理

```python
@app.get("/dashboard")
async def get_dashboard(session: AsyncSession = Depends(get_async_db_session)):
    task_repo = AsyncBaseRepository(Task, session)
    user_repo = AsyncBaseRepository(User, session)
    
    # 複数のカウントを並行実行
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

### エラーハンドリング付き並行処理

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
            
            # 成功したものだけフィルタ
            valid_results = [r for r in results if not isinstance(r, Exception)]
            return valid_results
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
            return []
```

### バッチ処理パターン

```python
async def process_tasks_in_batches(task_ids: List[int], batch_size: int = 10):
    """大量のタスクをバッチ処理"""
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # バッチに分割
        for i in range(0, len(task_ids), batch_size):
            batch_ids = task_ids[i:i + batch_size]
            
            # find_by_ids で一括取得
            tasks = await repo.find_by_ids(batch_ids)
            
            # 処理
            for task in tasks:
                task.status = 'processed'
            
            await repo.saves(tasks)
            
            # 少し待機（負荷軽減）
            await asyncio.sleep(0.1)
```

---

## 論理削除

AsyncBaseRepository は SoftDelete パターンをサポートしています。

### 論理削除の実行

```python
async def soft_delete_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 論理削除（deleted_at を設定）
        success = await repo.soft_delete(task_id)
        if success:
            print(f"Task {task_id} was soft deleted")
        else:
            print(f"Task {task_id} not found")
```

### 削除済みデータの復元

```python
async def restore_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 復元（deleted_at を NULL に）
        success = await repo.restore(task_id)
        if success:
            print(f"Task {task_id} was restored")
```

### 物理削除（完全削除）

```python
async def permanently_delete_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # データベースから完全削除（取り消し不可）
        success = await repo.permanent_delete(task_id)
        if success:
            print(f"Task {task_id} was permanently deleted")
```

### 削除済みデータの取得

```python
async def list_deleted_tasks():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 削除済みのみ取得
        deleted_tasks = await repo.find_deleted()
        
        # 特定期間より前に削除されたもの
        from datetime import datetime, timedelta, timezone
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        old_deleted = await repo.find_deleted_before(threshold)
        
        return {
            "all_deleted": deleted_tasks,
            "old_deleted": old_deleted
        }
```

### 削除済みデータを含めて取得

```python
# デフォルト（削除済みは除外）
tasks = await repo.find()

# 削除済みも含める
all_tasks = await repo.find(include_deleted=True)

# ID取得も同様
task = await repo.get_by_id(1, include_deleted=True)
```

---

## ベストプラクティス

### ✅ DO: セッション管理

```python
# Good: コンテキストマネージャーで自動管理
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
    # session は自動的にクローズされる

# Good: FastAPI の Depends で注入
@app.get("/tasks")
async def list_tasks(session: AsyncSession = Depends(get_async_db_session)):
    repo = AsyncBaseRepository(Task, session)
    return await repo.find()
```

```python
# Bad: セッションを手動管理（クローズ忘れのリスク）
session = AsyncSession(async_engine)
repo = AsyncBaseRepository(Task, session)
task = await repo.get_by_id(1)
await session.close()  # 忘れる可能性
```

### ✅ DO: Eager Loading の使用

```python
# Good: N+1 問題を回避
tasks = await repo.find(
    options=[joinedload(Task.user)]
)

# Bad: Lazy loading（N+1 問題発生）
tasks = await repo.find()
for task in tasks:
    print(task.user.name)  # 各タスクで個別クエリ
```

### ✅ DO: 並行処理の活用

```python
# Good: 独立したクエリは並行実行
tasks, users = await asyncio.gather(
    task_repo.find(),
    user_repo.find()
)

# Bad: 順次実行（遅い）
tasks = await task_repo.find()
users = await user_repo.find()
```

### ✅ DO: エラーハンドリング

```python
# Good: 適切なエラーハンドリング
try:
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await repo.save(task)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    raise HTTPException(status_code=500, detail="Database error")
```

### ✅ DO: カスタムリポジトリの作成

```python
# Good: ビジネスロジックをリポジトリに集約
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

### ❌ DON'T: リポジトリ内での並行処理

```python
# Bad: リポジトリメソッド内で asyncio.gather
class TaskRepository(AsyncBaseRepository[Task]):
    async def get_tasks_and_users(self):
        # これはやらない - 責務が不明確
        return await asyncio.gather(
            self.find(),
            user_repo.find()  # 他のリポジトリに依存
        )

# Good: エンドポイントで並行処理
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

### ❌ DON'T: 過度な eager loading

```python
# Bad: 不要な関連まで取得
tasks = await repo.find(
    options=[
        joinedload(Task.user).joinedload(User.profile),
        selectinload(Task.comments).joinedload(Comment.author),
        joinedload(Task.category).joinedload(Category.parent)
    ]
)

# Good: 必要なものだけ取得
tasks = await repo.find(
    options=[joinedload(Task.user)]
)
```

### ✅ DO: トランザクション管理

```python
# Good: 複数操作をトランザクションでまとめる
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    
    try:
        task1 = await repo.save(Task(title="Task 1"))
        task2 = await repo.save(Task(title="Task 2"))
        # commit は session close 時に自動実行
    except Exception:
        # rollback は自動実行
        raise
```

---

## 同期版との比較

### コード比較

**同期版 (BaseRepository)**:
```python
from repom.base_repository import BaseRepository
from repom.db import db_session

with db_session() as session:
    repo = BaseRepository(Task, session)
    task = repo.get_by_id(1)
    tasks = repo.find(filters=[Task.status == 'active'])
```

**非同期版 (AsyncBaseRepository)**:
```python
from repom.async_base_repository import AsyncBaseRepository
from repom.async_session import get_async_db_session

async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
    tasks = await repo.find(filters=[Task.status == 'active'])
```

### 主な変更点

1. `async with` でセッション取得
2. すべてのリポジトリメソッドに `await` が必要
3. 並行処理は `asyncio.gather` で実現

---

## まとめ

- **AsyncBaseRepository** は FastAPI など非同期フレームワークで使用
- すべてのメソッドは `async def` で `await` が必要
- `options` パラメータで eager loading をサポート（N+1 問題解決）
- `asyncio.gather` で並行処理が可能
- 論理削除（SoftDelete）もサポート
- カスタムリポジトリを作成してビジネスロジックを集約

詳細は以下のドキュメントも参照してください：

- [BaseRepository ガイド](repository_and_utilities_guide.md) - 同期版の詳細
- [Session Management ガイド](session_management_guide.md) - セッション管理
- [Testing ガイド](testing_guide.md) - AsyncBaseRepository のテスト方法
