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
| `get_by_id(id, include_deleted=False, options=None)` | ID で取得 | `Optional[T]` |
| `get_by(column, value)` | カラムで検索 | `List[T]` |
| `get_all()` | 全件取得 | `List[T]` |
| `find(params=None, filters=None, include_deleted=False, **kwargs)` | 条件検索 | `List[T]` |
| `find_by_ids(ids, include_deleted=False, **kwargs)` | ID リストで一括取得 | `List[T]` |
| `find_one(filters)` | 単一検索 | `Optional[T]` |
| `count(filters=None, include_deleted=False, params=None)` | 件数カウント | `int` |
| `count_by_params(params=None, include_deleted=False)` | FilterParams による件数カウント | `int` |
| `save(instance)` | 保存 | `T` |
| `saves(instances)` | 一括保存 | `None` |
| `dict_save(data)` | 辞書から保存 | `T` |
| `dict_saves(data_list)` | 辞書リストから一括保存 | `None` |
| `bulk_insert(objects)` | 一括作成 | `list[T]` |
| `bulk_update(values, filter_by=None, filters=None, allow_unfiltered=False, include_deleted=False)` | 一括更新 | `int` |
| `bulk_delete(filter_by=None, ids=None, filters=None, allow_unfiltered=False)` | 一括削除 | `int` |
| `bulk_permanent_delete(filter_by=None, ids=None, filters=None, allow_unfiltered=False)` | 物理一括削除 | `int` |
| `get_or_create(lookup, defaults=None)` | 一意キーで取得または作成 | `tuple[T, bool]` |
| `remove(instance)` | 削除 | `None` |
| `soft_delete` / `restore` / `permanent_delete` / `find_deleted` / `find_deleted_before` | 論理削除 API | [Soft Delete ガイド](../model/soft_delete_guide.md)を参照 |

`bulk_update()` と `bulk_delete()` は `filters=` を通じて SQLAlchemy 式も受け取ります。
これらの式は、該当する `filter_by=` および `ids=` の条件と AND で結合されます。
空でない `filters` も絞り込み条件を必須とする安全チェックを満たします。
`bulk_update()` の空の `filter_by` は、`filters=` も空の場合にエラーになります。
`bulk_delete()` と `bulk_permanent_delete()` は `filter_by`、`ids`、`filters` がすべて
空の場合にエラーになります。`bulk_update()` で
`filter_by` を省略し、`filters=` も空の場合は、更新する各辞書に `id` が必要です。
空でない `filters=` を指定した場合は、更新内容が条件に一致する各行へ適用されます。
`bulk_permanent_delete()` は、論理削除対応モデルも含め、常に物理削除を実行します。
`get_or_create(lookup, defaults=None)` は `(instance, created)` を返し、同時挿入で別の処理が
一意キーの行を先に作成した場合は、その行を再検索して返します。

`find()` の `filters=` はキーワードで指定してください。位置引数は `params` として解釈されます。
`find(params=...)` で使う各フィールドは `field_to_column` にマッピングするか、
`_build_filters()` で処理してください。未マッピングフィールドの詳細は
[FilterParams ガイド](repository_filter_params_guide.md#未マッピングフィールド)を参照してください。

`get_by(..., single=True)` の並び順と `get_by_id()` の挙動は
[order_by ガイド](order_by_guide.md#決定的な並び順)を参照してください。`get_all()` は全件を取得し、
`max_limit` の制限も適用しません。

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

読み取りや呼び出し側が commit を管理する場合は `get_reusable_sync_session()` /
`get_reusable_async_session()` を使います。これらは commit せず、終了時に `session.close()` で
未完了のトランザクションを破棄します。終了後も読み込み済みのオブジェクト属性は参照できますが、
遅延読み込みはできません。`get_db_session()` も commit しませんが、
`get_async_db_session()` は成功時に commit します。詳細は
[セッション管理パターンガイド](repository_session_patterns.md)を参照してください。

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

### `find()` をオーバーライドする

`find()` を独自に実装する場合は、`filters` と `include_deleted` 引数を受け取り、
検索条件へ統合してください。どちらかを無視すると、呼び出し側が要求していないレコードを
返したり、論理削除済みレコードを公開したりするおそれがあります。`get_by()`、
`get_by_id()`、`find_one()` はそれぞれ独自の条件付きクエリを実行するため、
オーバーライドした `find()` は呼び出しません。

検索と ID 取得の両方で SELECT 文の構築を変更する場合は、代わりに `_base_select()` を
オーバーライドしてください。たとえば、identity map にあるオブジェクトを再読み込みする
リポジトリでは、次のようにできます。

```python
def _base_select(self):
    return super()._base_select().execution_options(populate_existing=True)
```

このフックは、多くの標準 Repository 検索と ID 取得の SELECT 構築に使われますが、
モデルの読み込みすべてには適用されません。`get_or_create()` の初回・再試行 lookup は
直接 `select(self.model)` を構築します。lookup の等価条件と論理削除フィルタは適用されますが、
この hook で指定した `execution_options` などは適用されません。内部 session を使う保存系処理の
`session.refresh()` と `remove()` の `merge()` も、この hook を通りません。
`_base_select()` は tenant scoping 用の境界ではありません。ここでフィルタを追加せず、
認可や tenant 条件は各呼び出し側で明示してください。

### `populate_existing` が必要な場合

`populate_existing=True` はデータを最新にするためのオプションとして説明されることが
ありますが、マッピング方法によっては必須です。

`lazy="noload"` と宣言した relationship は、通常の読み込み時に未ロードのままにはならず、
コレクションなら空リスト、多対一なら `None` が設定されます。そのため SQLAlchemy は属性を
すでにロード済みと判断します。同じ行を明示的な eager-load `options` 付きで再取得しても、
クエリにはオプションが適用されますが属性は上書きされず、eager load が何もせずに終わります。

```
lazy="noload", plain read, then re-read WITH selectinload
  without populate_existing : []              # eager load silently does nothing
  with    populate_existing : [<Child ...>]
```

したがって、`lazy="noload"` の relationship とクエリ単位の load options を併用する
Repository では、その options を機能させるために `populate_existing=True` が必要です。
属性が未ロードではなく値を持つ状態になるほかの戦略でも同じです。

このフラグを使う主な理由はこれです。指定する前に次の節も確認してください。

### `populate_existing` と未 flush の変更

repom の session は、明示した flush のタイミングを保つため、継承した設定により
`autoflush=False` が既定です。そのため `_base_select()` で
`populate_existing=True` を使うと、Repository の読み込みでデータベースからインスタンスを
再読み込みし、session 内の未 flush の変更を破棄する場合があります。

保留中の変更を保持する必要がある場合は、読み込み前に flush してください。

```python
session.flush()
item = repository.get_by_id(item.id)
```

または、アプリケーションの `CONFIG_HOOK` で `config.autoflush = True` を設定すると、
SQLAlchemy の既定であるクエリ実行時の flush に戻せます。

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

`bulk_update()` は `filter_by={}` の場合も `filters=` が空のときだけ `ValueError` を送出します。
`filter_by` を省略し、`filters=` も空の場合は各更新辞書に `id` が必要です。

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
