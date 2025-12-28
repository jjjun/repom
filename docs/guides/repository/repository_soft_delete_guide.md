# SoftDelete ガイド（論理削除）

**目的**: repom の論理削除（SoftDelete）機能を理解する

**対象読者**: データの復元可能な削除が必要な開発者・AI エージェント

**関連ドキュメント**:
- [基礎編：CRUD操作](base_repository_guide.md) - 基本的なデータ操作
- [上級編：検索・フィルタ](repository_advanced_guide.md) - 削除済みデータの検索
- [非同期版](async_repository_guide.md) - AsyncBaseRepository での使用方法

---

## 📚 目次

1. [論理削除とは](#論理削除とは)
2. [モデルの設定](#モデルの設定)
3. [基本的な使い方](#基本的な使い方)
4. [削除済みデータの検索](#削除済みデータの検索)
5. [物理削除との違い](#物理削除との違い)
6. [実装パターン](#実装パターン)

---

## 論理削除とは

### 概要

**論理削除（Soft Delete）** は、データベースからレコードを物理的に削除せず、「削除済み」フラグを立てることでデータを非表示にする手法です。

### 物理削除との違い

| 項目 | 物理削除 | 論理削除 |
|------|---------|---------|
| データ | 完全に削除 | データベースに残る |
| 復元 | ❌ 不可能 | ✅ 可能 |
| 履歴 | ❌ 失われる | ✅ 保持される |
| パフォーマンス | 速い | やや遅い（フィルタが必要） |
| ディスク容量 | 節約できる | 増加する |

### いつ使うべきか

✅ **論理削除が適している場合**:
- ユーザーが誤って削除した場合に復元が必要
- 削除履歴を保持する必要がある（監査、コンプライアンス）
- 他のテーブルとの外部キー制約がある
- 削除されたデータを後で分析したい

❌ **物理削除が適している場合**:
- 完全に削除する必要がある（GDPR など）
- ディスク容量を節約したい
- 削除されたデータに価値がない
- 復元が不要

---

## モデルの設定

### SoftDeletableMixin の追加

論理削除を使用するには、モデルに `SoftDeletableMixin` を追加します。

```python
from repom.base_model_auto import BaseModelAuto
from repom.mixins import SoftDeletableMixin

class Task(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = 'tasks'
    
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50))
```

### Mixin が追加するカラム

`SoftDeletableMixin` は以下のカラムを自動的に追加します：

- `deleted_at: datetime | None` - 削除日時（削除されていない場合は NULL）
- `is_deleted: bool` - 削除フラグ（プロパティ、`deleted_at is not None` で判定）

### マイグレーション

Mixin を追加した後、Alembic でマイグレーションを作成します：

```bash
poetry run alembic revision --autogenerate -m "Add soft delete to tasks"
poetry run alembic upgrade head
```

---

## 基本的な使い方

### 論理削除（soft_delete）

```python
from repom.repositories import BaseRepository

# 同期版
repo = BaseRepository(Task, session=db_session)
success = repo.soft_delete(task_id=1)

if success:
    print("タスクを削除しました（復元可能）")
else:
    print("タスクが見つかりません")
```

```python
# 非同期版
from repom.async_base_repository import AsyncBaseRepository

repo = AsyncBaseRepository(Task, session=async_session)
success = await repo.soft_delete(task_id=1)
```

**動作**:
- `deleted_at` に現在時刻（UTC）を設定
- `is_deleted` が `True` になる
- データベースには残る

### 復元（restore）

```python
# 同期版
success = repo.restore(task_id=1)

if success:
    print("タスクを復元しました")
```

```python
# 非同期版
success = await repo.restore(task_id=1)
```

**動作**:
- `deleted_at` を `NULL` に設定
- `is_deleted` が `False` になる
- 通常の検索で再び表示される

### 物理削除（permanent_delete）

論理削除されたデータを完全に削除：

```python
# 同期版
success = repo.permanent_delete(task_id=1)

if success:
    print("タスクを完全に削除しました（復元不可）")
```

```python
# 非同期版
success = await repo.permanent_delete(task_id=1)
```

**警告**: この操作は取り消せません。データベースから完全に削除されます。

### 通常の削除（remove）

`remove()` メソッドは物理削除を行います：

```python
# 物理削除（SoftDelete を使わない）
task = repo.get_by_id(1)
repo.remove(task)  # データベースから完全削除
```

---

## 削除済みデータの検索

### デフォルトの動作

**重要**: 論理削除済みのデータは、デフォルトで検索結果から除外されます。

```python
# 削除済みは自動的に除外される
tasks = repo.find()  # is_deleted=False のみ
task = repo.get_by_id(1)  # 削除済みの場合は None
```

### 削除済みを含めて取得

```python
# 削除済みも含める
all_tasks = repo.find(include_deleted=True)

# ID で取得（削除済みも含める）
task = repo.get_by_id(1, include_deleted=True)

# カラム検索（削除済みも含める）
tasks = repo.get_by('status', 'active', include_deleted=True)
```

### 削除済みのみ取得

```python
# 削除済みのみ
deleted_tasks = repo.find_deleted()

# 特定期間より前に削除されたもの
from datetime import datetime, timedelta, timezone

threshold = datetime.now(timezone.utc) - timedelta(days=30)
old_deleted = repo.find_deleted_before(threshold)
```

```python
# 非同期版
deleted_tasks = await repo.find_deleted()
old_deleted = await repo.find_deleted_before(threshold)
```

### find_by_ids での使用

```python
# デフォルト（削除済みは除外）
tasks = repo.find_by_ids([1, 2, 3])

# 削除済みも含める
tasks = repo.find_by_ids([1, 2, 3], include_deleted=True)
```

詳細は [上級編：find_by_ids()](repository_advanced_guide.md#find_by_ids-メソッド---効率的な一括取得) を参照してください。

---

## 物理削除との違い

### コード比較

```python
# 物理削除（従来の方法）
task = repo.get_by_id(1)
repo.remove(task)
# → データベースから完全削除、復元不可

# 論理削除（SoftDelete）
repo.soft_delete(1)
# → deleted_at を設定、復元可能

# 復元
repo.restore(1)
# → deleted_at を NULL に、再び表示される
```

### データベースの状態

**物理削除**:
```sql
-- 削除前
SELECT * FROM tasks WHERE id = 1;
-- id | title | status
-- 1  | Task1 | active

-- 削除後
DELETE FROM tasks WHERE id = 1;
SELECT * FROM tasks WHERE id = 1;
-- (結果なし)
```

**論理削除**:
```sql
-- 削除前
SELECT * FROM tasks WHERE id = 1;
-- id | title | status | deleted_at
-- 1  | Task1 | active | NULL

-- 削除後
UPDATE tasks SET deleted_at = '2025-12-28 10:00:00' WHERE id = 1;
SELECT * FROM tasks WHERE id = 1 AND deleted_at IS NULL;
-- (結果なし、deleted_at フィルタで除外)

SELECT * FROM tasks WHERE id = 1;
-- id | title | status | deleted_at
-- 1  | Task1 | active | 2025-12-28 10:00:00
```

---

## 実装パターン

### パターン1: FastAPI での使用

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from repom.repositories import BaseRepository

router = APIRouter()

@router.delete("/tasks/{task_id}")
def soft_delete_task(
    task_id: int,
    session: Session = Depends(get_db_session)
):
    """タスクを論理削除"""
    repo = BaseRepository(Task, session)
    
    if not repo.soft_delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}


@router.post("/tasks/{task_id}/restore")
def restore_task(
    task_id: int,
    session: Session = Depends(get_db_session)
):
    """タスクを復元"""
    repo = BaseRepository(Task, session)
    
    if not repo.restore(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task restored successfully"}


@router.get("/tasks/deleted")
def list_deleted_tasks(session: Session = Depends(get_db_session)):
    """削除済みタスク一覧"""
    repo = BaseRepository(Task, session)
    deleted = repo.find_deleted()
    return deleted
```

### パターン2: カスタムリポジトリ

```python
from repom.repositories import BaseRepository
from typing import List
from datetime import datetime, timedelta, timezone

class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: Session = None):
        super().__init__(Task, session)
    
    def cleanup_old_deleted(self, days: int = 30) -> int:
        """古い削除済みデータを物理削除"""
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        old_deleted = self.find_deleted_before(threshold)
        
        count = 0
        for task in old_deleted:
            if self.permanent_delete(task.id):
                count += 1
        
        return count
    
    def get_active_with_recently_deleted(self, days: int = 7) -> List[Task]:
        """アクティブ + 最近削除されたタスクを取得"""
        recent_threshold = datetime.now(timezone.utc) - timedelta(days=days)
        
        # アクティブなタスク
        active = self.find(filters=[Task.status == 'active'])
        
        # 最近削除されたタスク
        recent_deleted = self.find_deleted_before(
            before=datetime.now(timezone.utc)
        )
        recent_deleted = [
            t for t in recent_deleted
            if t.deleted_at and t.deleted_at >= recent_threshold
        ]
        
        return active + recent_deleted
```

### パターン3: バッチ処理

```python
def cleanup_old_deleted_tasks(days: int = 90):
    """90日以上前に削除されたタスクを物理削除"""
    from repom.database import db_session
    
    with db_session() as session:
        repo = BaseRepository(Task, session)
        
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        old_deleted = repo.find_deleted_before(threshold)
        
        print(f"Found {len(old_deleted)} old deleted tasks")
        
        for task in old_deleted:
            print(f"Permanently deleting task {task.id}: {task.title}")
            repo.permanent_delete(task.id)
        
        print("Cleanup completed")
```

### パターン4: 非同期版（FastAPI）

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from repom.async_base_repository import AsyncBaseRepository

router = APIRouter()

@router.delete("/tasks/{task_id}")
async def soft_delete_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    """タスクを論理削除（非同期）"""
    repo = AsyncBaseRepository(Task, session)
    
    if not await repo.soft_delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}


@router.get("/tasks/deleted")
async def list_deleted_tasks(
    session: AsyncSession = Depends(get_async_db_session)
):
    """削除済みタスク一覧（非同期）"""
    repo = AsyncBaseRepository(Task, session)
    deleted = await repo.find_deleted()
    return deleted
```

---

## ベストプラクティス

### ✅ DO: 削除理由を記録

```python
# カスタムモデルで削除理由を追加
class Task(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = 'tasks'
    
    title: Mapped[str] = mapped_column(String(200))
    deleted_reason: Mapped[str | None] = mapped_column(String(500))

# 使用
task = repo.get_by_id(1)
task.deleted_reason = "User requested deletion"
repo.soft_delete(1)
```

### ✅ DO: 定期的にクリーンアップ

```python
# 古い削除済みデータを定期的に物理削除
def scheduled_cleanup():
    """90日以上前の削除済みデータをクリーンアップ"""
    repo = BaseRepository(Task, session=db_session)
    threshold = datetime.now(timezone.utc) - timedelta(days=90)
    old_deleted = repo.find_deleted_before(threshold)
    
    for task in old_deleted:
        repo.permanent_delete(task.id)
```

### ✅ DO: 削除済みデータへのアクセス制御

```python
# 管理者のみ削除済みを閲覧可能
@router.get("/tasks/deleted")
def list_deleted_tasks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    repo = BaseRepository(Task, session)
    return repo.find_deleted()
```

### ❌ DON'T: 削除済みデータを無制限に蓄積

```python
# Bad: 削除済みデータが永遠に残る
# → ディスク容量を圧迫、パフォーマンス低下

# Good: 定期的にクリーンアップ
# → 必要な期間だけ保持
```

### ❌ DON'T: センシティブなデータの論理削除

```python
# Bad: パスワード、クレジットカード情報などを論理削除
# → GDPR 違反のリスク

# Good: センシティブなデータは物理削除
task = repo.get_by_id(1)
repo.remove(task)  # 完全削除
```

---

## トラブルシューティング

### エラー: Model does not support soft delete

```python
# エラー
repo.soft_delete(1)
# ValueError: Task does not support soft delete.
# Add SoftDeletableMixin to the model.
```

**解決方法**: モデルに `SoftDeletableMixin` を追加

```python
class Task(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = 'tasks'
    # ...
```

### 削除済みデータが表示されない

```python
# 削除済みは自動的に除外される
tasks = repo.find()  # 削除済みは含まれない

# 削除済みも含めるには
tasks = repo.find(include_deleted=True)
```

### 復元できない

```python
# 物理削除されたデータは復元不可
task = repo.get_by_id(1)
repo.remove(task)  # 物理削除
repo.restore(1)  # False（復元できない）

# 論理削除なら復元可能
repo.soft_delete(1)
repo.restore(1)  # True（復元成功）
```

---

## まとめ

- **論理削除** は復元可能な削除（`deleted_at` を設定）
- **物理削除** は完全な削除（データベースから削除）
- `SoftDeletableMixin` をモデルに追加して使用
- デフォルトで削除済みは検索から除外される
- `include_deleted=True` で削除済みも取得可能
- 定期的なクリーンアップを推奨

## 関連ドキュメント

- **[基礎編：CRUD操作](base_repository_guide.md)**: 基本的なデータ操作
- **[上級編：検索・フィルタ](repository_advanced_guide.md)**: find_by_ids() での使用方法
- **[非同期版](async_repository_guide.md)**: AsyncBaseRepository での使用方法
- **[SoftDeletableMixin ソースコード](../../../repom/mixins/soft_delete.py)**: 実装の詳細

---

**最終更新**: 2025-12-28  
**対象バージョン**: repom v2.0+
