# BaseRepository ガイド（基礎編）

**目的**: repom の `BaseRepository` によるデータアクセスの基本を理解する

**対象読者**: repom を初めて使う開発者・AI エージェント

**関連ドキュメント**:
- [上級編：検索・フィルタ・options](repository_advanced_guide.md) - 複雑な検索、eager loading、パフォーマンス最適化
- [FilterParams ガイド](repository_filter_params_guide.md) - 検索パラメータ (FilterParams) の定義と使用方法

---

## 📚 目次

1. [基本的な使い方](#基本的な使い方)
2. [CRUD 操作](#crud-操作)
3. [実装パターン：シンプルな CRUD](#実装パターンシンプルな-crud)
4. [トラブルシューティング](#トラブルシューティング)

---

## 基本的な使い方

### リポジトリの作成

#### 推奨パターン: __init__ を省略（型推論）

```python
from repom import BaseRepository
from your_project.models import Task
from repom.database import get_reusable_sync_transaction

# カスタムリポジトリを定義（推奨）
class TaskRepository(BaseRepository[Task]):
    pass

# インスタンス化（モデル名の指定が不要）
with get_reusable_sync_transaction() as session:
    repo = TaskRepository(session=session)
```

**メリット**:
- モデル指定が不要（型パラメータから自動推論）
- カスタムメソッドを追加しやすい
- コードが読みやすい

#### 代替パターン: BaseRepository を直接使用

```python
from repom import BaseRepository
from repom.database import get_reusable_sync_transaction
from your_project.models import Task

# カスタムリポジトリが不要な場合
with get_reusable_sync_transaction() as session:
    repo = BaseRepository(Task, session=session)
```

### 主要メソッド一覧

| メソッド | 用途 | 戻り値 |
|---------|------|--------|
| `get_by_id(id)` | ID で取得 | `Optional[T]` |
| `get_by(column, value)` | カラムで検索 | `List[T]` |
| `get_all()` | 全件取得 | `List[T]` |
| `find(params=None, filters=None, include_deleted=False, **kwargs)` | 条件検索 | `List[T]` |
| `find_one(filters)` | 単一検索 | `Optional[T]` |
| `count(filters)` | 件数カウント | `int` |
| `save(instance)` | 保存 | `T` |
| `saves(instances)` | 一括保存 | `None` |
| `bulk_insert(objects)` | 一括作成 | `list[T]` |
| `bulk_update(values, filter_by=None, allow_unfiltered=False, include_deleted=False)` | 一括更新 | `int` |
| `bulk_delete(filter_by=None, ids=None, allow_unfiltered=False)` | 一括削除 | `int` |
| `remove(instance)` | 削除 | `None` |

`find()` の `filters=` はキーワードで指定してください。位置引数は `params` として解釈されます。

`get_by(..., single=True)` と `get_by_id()` は `ORDER BY` を適用しません。`get_by(..., single=True)` で複数行が一致する場合、返される行は決定的ではありません。`get_all()` は全件を取得し、`max_limit` の制限も適用しません。

---

## CRUD 操作

### Create（作成）

```python
# 内部セッション: 自動 commit
repo = TaskRepository()
task = Task(title="新しいタスク", status="active")
saved_task = repo.save(task)  # commit が自動実行

# 外部セッション: 呼び出し側が commit
from repom.database import get_reusable_sync_transaction

with get_reusable_sync_transaction() as session:
    repo = TaskRepository(session=session)
    task = Task(title="新しいタスク", status="active")
    saved_task = repo.save(task)  # flush のみ、commit は with 終了時

    # 辞書から保存（同様の動作）
    task = repo.dict_save({"title": "タスク2", "status": "pending"})

    # 複数保存
    tasks = [Task(title=f"タスク{i}") for i in range(3)]
    repo.saves(tasks)

    # 辞書リストから保存
    data_list = [{"title": f"タスク{i}"} for i in range(3)]
    repo.dict_saves(data_list)

    # bulk_insert は保存済みオブジェクトを返す
    tasks = repo.bulk_insert([Task(title=f"タスク{i}") for i in range(100)])
```

**注意**: 外部セッションを使用する場合、`save()` / `saves()` は `flush()` のみを実行します。
変更を確定するには、`with` ブロックを抜けるか、明示的に `session.commit()` を呼んでください。

**用途別の使い分け**:
- FastAPI Depends: 読み取りは `Depends(get_db_session)`、書き込みは `Depends(get_db_transaction, scope="function")`
- sync の反復 transaction（task/worker/CLI）: `get_reusable_sync_transaction()`
- one-shot script（終了時 dispose を含む）: `get_standalone_sync_transaction()`
- async パターン: `Depends(get_async_db_session)` / `Depends(get_async_db_transaction, scope="function")` / `get_standalone_async_transaction()`

**詳細**: [セッション管理パターンガイド](repository_session_patterns.md)

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

`get_by()` の第一引数は信頼できるカラム名であることが前提です。リクエスト
のフィールド名をそのまま渡す場合は `allowed_filter_columns` でホワイト
リストを設定してください（詳細は
[検索カラムの制限](repository_advanced_guide.md#get_by--bulk_update--bulk_delete-の検索カラムの制限)）。

### Overriding `find()`

Custom `find()` implementations must accept and merge the `filters` and
`include_deleted` arguments. Ignoring either argument can return records that
callers did not request or expose soft-deleted records. `get_by()`,
`get_by_id()`, and `find_one()` execute their own constrained queries, so they
do not call an overridden `find()` implementation.

To customise statement construction for both searches and identity lookups,
override `_base_select()` instead. For example, a repository that needs to
refresh identity-mapped objects can use:

```python
def _base_select(self):
    return super()._base_select().execution_options(populate_existing=True)
```

This hook applies to every repository query that selects model instances.
Do not add filters in `_base_select()`; each caller owns its filters.

### When `populate_existing` is required

`populate_existing=True` is often described as a freshness option, but for some
mapping styles it is not optional at all.

A relationship declared `lazy="noload"` is left *populated* by an ordinary read -
an empty list for a collection, `None` for a many-to-one - rather than being left
unloaded. SQLAlchemy therefore considers the attribute already loaded. A later
read of the same row with explicit eager-load `options` applies those options to
the statement but does not overwrite the attribute, so the eager load silently
does nothing:

```
lazy="noload", plain read, then re-read WITH selectinload
  without populate_existing : []              # eager load silently does nothing
  with    populate_existing : [<Child ...>]
```

So a repository that combines `lazy="noload"` relationships with per-query load
options needs `populate_existing=True` for those options to have any effect. The
same applies to any strategy that leaves the attribute populated rather than
unloaded.

This is the usual reason to reach for the flag. Read the next section before
doing so.

### `populate_existing` and unflushed changes

repom sessions default to `autoflush=False`, an inherited setting that preserves
explicit flush timing. When `_base_select()` uses `populate_existing=True`, a
repository read can therefore discard an unflushed in-session change by
reloading the instance from the database.

Flush before the read when the pending change must be retained:

```python
session.flush()
item = repository.get_by_id(item.id)
```

Alternatively, set `config.autoflush = True` in the application's
`CONFIG_HOOK` to restore SQLAlchemy's default query-time flush behavior.

**関連モデルの取得（N+1 問題の解決）** については [上級編](repository_advanced_guide.md#eager-loadingn1問題の解決) を参照してください。
`options` にコレクション関連への `joinedload()` を渡した場合も、結果は
`Result.unique()` で重複排除されるため、各レコードは1回だけ返ります。

### Update（更新）

```python
# インスタンスを取得して更新
task = repo.get_by_id(1)
task.status = 'completed'
repo.save(task)

# または BaseModel の update_from_dict を使用（allowed_fields か
# クラス属性 updatable_fields でアローリストを指定する必要がある）
task.update_from_dict({"status": "completed"}, allowed_fields={"status"})
repo.save(task)

# ID を含む dict で複数行を更新
updated = repo.bulk_update([
    {"id": 1, "status": "completed"},
    {"id": 2, "status": "archived"},
])

# 共通条件に一致する行を同じ値で更新
updated = repo.bulk_update(
    [{"status": "archived"}],
    filter_by={"status": "stale"},
)
```

### Delete（削除）

```python
task = repo.get_by_id(1)
repo.remove(task)  # 物理削除（完全削除）

# 複数 ID をまとめて削除
deleted = repo.bulk_delete(ids=[1, 2, 3])

# 条件に一致する行をまとめて削除
deleted = repo.bulk_delete(filter_by={"status": "archived"})

# filter_by も ids も指定しない場合は ValueError
# 全件を対象にする場合は明示的に allow_unfiltered=True を渡す
deleted = repo.bulk_delete(allow_unfiltered=True)
```

**論理削除（復元可能な削除）** については [SoftDelete ガイド](../model/soft_delete_guide.md) を参照してください。
`bulk_delete()` は `SoftDeletableMixin` 対応モデルでは物理削除ではなく `deleted_at` を更新します。

`bulk_update()` も `filter_by` に空の dict を渡すと同様に `ValueError` を送出します。
`filter_by` 未指定時は各 dict の `id` を条件に使うため、この制限の対象外です。

`bulk_update()` はデフォルトで論理削除済みの行を除外し、`include_deleted=True` を指定すると更新対象に含めます。`bulk_delete()` は論理削除対応モデルでは未削除の行だけを対象にします。同期版の `bulk_update()` / `bulk_delete()` は外部セッションでも `expire_all()` を呼びますが、非同期版は呼びません。

---

## 実装パターン：シンプルな CRUD

```python
# リポジトリ定義
class UserRepository(BaseRepository[User]):
    pass

# 使用例
with get_reusable_sync_transaction() as session:
    repo = UserRepository(session=session)

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

---

## トラブルシューティング

### よくあるエラー

#### 1. `AttributeError: Unknown column on Task`

```python
# ❌ 間違い
tasks = repo.get_by('wrong_column', 'value')  # AttributeError: Unknown column on Task

# ✅ 正しい
tasks = repo.get_by('status', 'active')
```

**解決方法**: モデルに存在するカラム名を使用する

`get_by()` で不明なカラム名を指定すると `AttributeError: Unknown column on Task` が発生します。モデルに `id` カラムがない場合の `get_by_id()` と `bulk_delete(ids=...)` は、それぞれ別の `AttributeError: Column 'id' does not exist` になります。

#### 2. セッションスコープの落とし穴

```python
from repom.database import get_reusable_sync_transaction

# ❌ 外部セッションに結び付けたリポジトリを with の外で使う
with get_reusable_sync_transaction() as session:
    repo = TaskRepository(session=session)
repo.save(Task(title="タスク"))  # flush のみで commit されず、書き込みは確定しない

# ✅ 書き込みを with ブロック内で完了する
with get_reusable_sync_transaction() as session:
    repo = TaskRepository(session=session)
    repo.save(Task(title="タスク"))  # with 終了時に commit

# ❌ 内部セッションで取得した後、未ロードの relationship を参照する
repo = TaskRepository()
task = repo.get_by_id(1)
comments = task.comments  # DetachedInstanceError

# ✅ find() の options で relationship を eager load する
from sqlalchemy.orm import selectinload

task = repo.find(
    filters=[Task.id == 1],
    options=[selectinload(Task.comments)],
    limit=1,
)[0]
comments = task.comments
```

session-less のリポジトリは呼び出しごとに内部セッションを開くため、長時間経過してもこの理由ではエラーになりません。外部セッションに結び付けたリポジトリは `with` ブロック内で使ってください。内部セッションで取得したインスタンスは `expunge_all()` により detach されるため、後から未ロードの relationship を参照すると `DetachedInstanceError` になります。

### デバッグのヒント

```python
# クエリをログ出力
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# 取得したデータを確認
task = repo.get_by_id(1)
if task:
    print(f"Found: {task.to_dict()}")
else:
    print("Not found")
```

---

## 次のステップ

- **[上級編：検索・フィルタ・options](repository_advanced_guide.md)** - 複雑な検索、ソート、ページング、N+1問題の解決
- **[FilterParams ガイド](repository_filter_params_guide.md)** - 検索パラメータ (FilterParams) の定義と使用方法

## 関連ドキュメント

- **[auto_import_models ガイド](../features/auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseRepository ソースコード](../../../repom/repositories/base_repository.py)**: 実装の詳細

---

**最終更新**: 2025-12-28  
**対象バージョン**: repom v2.0+
