# BaseRepository ガイド（基礎編）

**目的**: repom の `BaseRepository` によるデータアクセスの基本を理解する

**対象読者**: repom を初めて使う開発者・AI エージェント

**関連ドキュメント**:
- [上級編：検索・フィルタ・options](repository_advanced_guide.md) - 複雑な検索、eager loading、パフォーマンス最適化
- [FastAPI 統合編：FilterParams](repository_filter_params_guide.md) - FastAPI での検索パラメータ処理

---

## 📚 目次

1. [基本的な使い方](#基本的な使い方)
2. [CRUD 操作](#crud-操作)
3. [実装パターン：シンプルな CRUD](#実装パターンシンプルな-crud)
4. [トラブルシューティング](#トラブルシューティング)

---

## 基本的な使い方

### リポジトリの作成

#### 推奨パターン: カスタム __init__ を定義

```python
from repom import BaseRepository
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
from repom import BaseRepository
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
# 内部セッション: 自動 commit
repo = TaskRepository()
task = Task(title="新しいタスク", status="active")
saved_task = repo.save(task)  # commit が自動実行

# 外部セッション: 呼び出し側が commit
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = TaskRepository(session)
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
```

**注意**: 外部セッションを使用する場合、`save()` / `saves()` は `flush()` のみを実行します。
変更を確定するには、`with` ブロックを抜けるか、明示的に `session.commit()` を呼んでください。

**詳細**: [セッション管理パターンガイド](repository_session_patterns.md#トランザクション管理の詳細)

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

**関連モデルの取得（N+1 問題の解決）** については [上級編](repository_advanced_guide.md#eager-loadingn1-問題の解決) を参照してください。

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
repo.remove(task)  # 物理削除（完全削除）
```

**論理削除（復元可能な削除）** については [SoftDelete ガイド](repository_soft_delete_guide.md) を参照してください。

---

## 実装パターン：シンプルな CRUD

```python
# リポジトリ定義
class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session = None):
        super().__init__(User, session)

# 使用例
repo = UserRepository(session=db_session)

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

#### 1. `AttributeError: Column '...' does not exist`

```python
# ❌ 間違い
tasks = repo.get_by('wrong_column', 'value')

# ✅ 正しい
tasks = repo.get_by('status', 'active')
```

**解決方法**: モデルに存在するカラム名を使用する

#### 2. セッションエラー

```python
# ❌ セッションが閉じている
repo = TaskRepository()
# ... 長時間経過 ...
task = repo.get_by_id(1)  # エラー

# ✅ 新しいセッションを使用
from repom.database import db_session
repo = TaskRepository(session=db_session)
```

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
- **[FastAPI 統合編：FilterParams](repository_filter_params_guide.md)** - FastAPI での検索パラメータ処理

## 関連ドキュメント

- **[auto_import_models ガイド](../core/auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseModelAuto ガイド](../features/base_model_auto_guide.md)**: スキーマ自動生成
- **[BaseRepository ソースコード](../../../repom/repositories/base_repository.py)**: 実装の詳細

---

**最終更新**: 2025-12-28  
**対象バージョン**: repom v2.0+
