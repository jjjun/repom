# AsyncBaseRepository ガイド

**目的**: repom の `AsyncBaseRepository` による非同期データアクセスパターンを理解する

**対象読者**: FastAPI など非同期フレームワークで repom を使う開発者、AI エージェント

---

## 📚 目次

1. [はじめに](#はじめに)
2. [基本的な使い方](#基本的な使い方)
3. [FastAPI 統合](#fastapi-統合)
4. [非同期 CRUD 操作](#非同期-crud-操作)
5. [検索とフィルタリング](#検索とフィルタリング)
6. [Eager Loading（N+1 問題の解決）](#eager-loading)
7. [並行処理パターン](#並行処理パターン)
8. [ベストプラクティス](#ベストプラクティス)

---

## はじめに

### AsyncBaseRepository とは

`AsyncBaseRepository` は `BaseRepository` の完全な非同期版です。すべてのメソッドは `async def` で定義され、`AsyncSession` を使用してデータベース操作を行います。

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
from repom import AsyncBaseRepository
from repom.database import get_async_db_session
from your_project.models import Task
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# FastAPI Depends パターンで使用（推奨）
async def get_task(task_id: int, session: AsyncSession = Depends(get_async_db_session)):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    return task
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

### カスタムリポジトリを使う場合

```python
from typing import List
from repom import AsyncBaseRepository

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
# FastAPI エンドポイントでの使用例
@app.post("/tasks")
async def create_task(
    task_data: dict,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    
    # 1件保存
    task = Task(title=task_data["title"], status="active")
    saved_task = await repo.save(task)
    
    # 辞書から保存
    task = await repo.dict_save({"title": "タスク2", "status": "pending"})
    
    # 複数保存
    tasks = [Task(title=f"タスク{i}") for i in range(3)]
    await repo.saves(tasks)
    
    # 辞書リストから保存
    data_list = [{"title": f"タスク{i}"} for i in range(3)]
    await repo.dict_saves(data_list)
    
    return saved_task
```

### Read（取得）

```python
# FastAPI エンドポイントでの使用例
@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    
    # ID で取得
    task = await repo.get_by_id(task_id)
    
    # カラムで検索（複数件）
    active_tasks = await repo.get_by('status', 'active')
    
    # 単一取得（single=True）
    task = await repo.get_by('title', 'タスク1', single=True)
    
    # 全件取得
    all_tasks = await repo.get_all()
    
    return task
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
        
        # 物理削除（完全削除）
        task = await repo.get_by_id(task_id)
        if task:
            await repo.remove(task)
```

---

## 検索とフィルタリング

非同期版でも検索・フィルタリング機能は同期版と同じです。詳細は **[Repository 上級ガイド](repository_advanced_guide.md)** を参照してください。

### クイックリファレンス

```python
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    
    # 基本検索
    tasks = await repo.find(filters=[Task.status == 'active'])
    
    # ページネーション
    tasks = await repo.find(offset=0, limit=20, order_by='created_at:desc')
    
    # カウント
    count = await repo.count(filters=[Task.status == 'active'])
```

詳細なフィルタリングパターン（AND/OR、LIKE、IN句など）は [Repository 上級ガイド](repository_advanced_guide.md#検索とフィルタリング) を参照してください。

---

## Eager Loading（N+1 問題の解決）

非同期版でも Eager Loading の仕組みは同期版と同じです。詳細は **[Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題の解決)** を参照してください。

### クイックリファレンス

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

詳細な使い方、パフォーマンス比較、ベストプラクティスは [Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題の解決) を参照してください。

### default_options による自動適用

```python
class TaskRepository(AsyncBaseRepository[Task]):
    # クラス属性で持つ（推奨）
    default_options = [
        joinedload(Task.user),
        selectinload(Task.comments)
    ]

# すべての取得メソッドで自動適用
repo = TaskRepository(session=session)
tasks = await repo.find()  # user と comments が自動ロード
task = await repo.get_by_id(1)  # 同じく自動適用
```

詳細は [Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題の解決) を参照してください。

---

## カスタムリポジトリ

ビジネスロジックを含むカスタムリポジトリの作成方法は **[Repository 上級ガイド](repository_advanced_guide.md#カスタムリポジトリ)** を参照してください。

### クイックリファレンス

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

複雑な検索ロジック、関連モデル操作、ビジネスロジック統合の詳細は [Repository 上級ガイド](repository_advanced_guide.md#カスタムリポジトリ) を参照してください。

---

## 論理削除（SoftDelete）

論理削除機能の使い方は **[SoftDelete ガイド](repository_soft_delete_guide.md)** を参照してください。非同期版の実装も含まれています。

### クイックリファレンス

```python
# 論理削除
await repo.soft_delete(task_id)

# 復元
await repo.restore(task_id)

# 削除済みを含めて検索
tasks = await repo.find(include_deleted=True)

# 削除済みのみ取得
deleted_tasks = await repo.find_deleted()
```

詳細は [SoftDelete ガイド](repository_soft_delete_guide.md) を参照してください。

---

## 非同期特有の機能

以下のセクションは AsyncBaseRepository に特有の機能です。

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
            
            # 少し待つ（負荷軽減）
            await asyncio.sleep(0.1)
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

### ❌ DON'T: リポジトリ内部の並行処理

```python
# Bad: リポジトリメソッド内部で asyncio.gather
class TaskRepository(AsyncBaseRepository[Task]):
    async def get_tasks_and_users(self):
        # これはやめる - 責務が不明確
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
from repom import BaseRepository
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:
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

1. `async with` でセッション取得
2. すべてのリポジトリメソッドに `await` が必要
3. 並行処理は `asyncio.gather` で実現

---

## まとめ

### AsyncBaseRepository の特徴

- **FastAPI など非同期フレームワークで使用**
- すべてのメソッドは `async def` で `await` が必要
- **並行処理**: `asyncio.gather` で複数クエリを並行実行
- **セッション管理**: `async with` または FastAPI の `Depends` で管理

### 機能別ガイド

| 機能 | ガイド | 概要 |
|------|--------|------|
| 基本的な CRUD | [BaseRepository ガイド](base_repository_guide.md) | 取得・作成・更新・削除 |
| 検索・フィルタリング | [Repository 上級ガイド](repository_advanced_guide.md#検索とフィルタリング) | find(), ページング、ソート |
| Eager Loading | [Repository 上級ガイド](repository_advanced_guide.md#eager-loadingn1問題の解決) | N+1 問題の解決、default_options |
| カスタムリポジトリ | [Repository 上級ガイド](repository_advanced_guide.md#カスタムリポジトリ) | ビジネスロジックの統合 |
| 論理削除 | [SoftDelete ガイド](repository_soft_delete_guide.md) | soft_delete, restore |
| FastAPI 統合 | [FilterParams ガイド](repository_filter_params_guide.md) | クエリパラメータの型安全処理 |
| テスト | [Testing ガイド](../testing/testing_guide.md) | 非同期テストのベストプラクティス |

### 非同期版の利点

✅ **高並行性**: 複数のクエリを並行実行できる  
✅ **I/O効率**: データベース待機中に他の処理を実行  
✅ **FastAPI統合**: Depends パターンでシームレスに統合  
✅ **スケーラビリティ**: 多数の同時リクエストを効率的に処理

### 次のステップ

1. **基礎を学ぶ**: [BaseRepository ガイド](base_repository_guide.md) で CRUD 操作を理解
2. **高度な検索**: [Repository 上級ガイド](repository_advanced_guide.md) で検索パターンを学習
3. **FastAPI統合**: [FilterParams ガイド](repository_filter_params_guide.md) で実践的な統合を実装
4. **並行処理**: このガイドの「並行処理パターン」を活用

---

**最終更新**: 2025-01-23  
**対象バージョン**: repom v2.0+
