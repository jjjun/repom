# Repository セッション管理パターンガイド

**目的**: BaseRepository でのセッション管理の仕組みと推奨パターンを理解する

**対象読者**: repom を使ってリポジトリパターンを実装する開発者、AI エージェント

---

## 📚 目次

1. [概要](#概要)
2. [BaseRepository のセッション管理の仕組み](#baserepository-のセッション管理の仕組み)
3. [推奨パターン](#推奨パターン)
4. [実装例](#実装例)
5. [よくある間違い](#よくある間違い)
6. [パターン選択ガイド](#パターン選択ガイド)

---

## 概要

`BaseRepository` は **`session=None` を許容** し、セッションが提供されていない場合は自動的に `get_db_session()` を使用します。これにより、シンプルな使い方から高度なトランザクション制御まで、柔軟な実装が可能です。

**重要**: Repository の `__init__` で `session is None` をチェックして `ValueError` を raise する必要は **ありません**。BaseRepository が自動的に処理します。

---

## BaseRepository のセッション管理の仕組み

### 内部実装

```python
class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: Optional[Session] = None):
        self.model = model
        self.session = session  # None でも OK

    def get_by_id(self, id: int) -> Optional[T]:
        # session が None の場合、get_db_session() を使用
        if self.session is None:
            with get_db_session() as session:
                return session.query(self.model).filter_by(id=id).first()
        else:
            # 渡されたセッションを使用
            return self.session.query(self.model).filter_by(id=id).first()
```

**ポイント**:
- `session=None` でインスタンス化可能
- 各メソッドで `self.session is None` をチェック
- None の場合は `get_db_session()` で自動セッション作成
- 提供されている場合はそれを使用

---

## 推奨パターン

### パターン 1: セッションなし（最もシンプル）

**特徴**:
- ✅ コードが最もシンプル
- ✅ 単純な CRUD 操作に最適
- ❌ トランザクション制御なし（各操作が個別コミット）
- ❌ 複数操作をアトミックにできない

```python
from repom import BaseRepository
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 使い方
repo = VoiceScriptRepository()
script = repo.get_by_id(1)
scripts = repo.get_all()
```

**適用場面**:
- 読み取り専用の操作
- 単一レコードの作成・更新・削除
- トランザクション制御が不要な場合

---

### パターン 2: 明示的トランザクション（推奨）

**特徴**:
- ✅ 複数操作をアトミックに実行可能
- ✅ エラー時は自動ロールバック
- ✅ トランザクション制御が明確
- ⚠️ やや冗長（with 文が必要）

**重要な動作**:
- 外部セッションを渡した場合、Repository の `save()` / `saves()` / `remove()` は `commit()` を実行しません
- 代わりに `flush()` のみが実行され、変更はトランザクション内で保留されます
- `commit()` は `with` ブロック終了時（または明示的な呼び出し）まで実行されません

```python
from repom.database import _db_manager
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 使い方
with _db_manager.get_sync_transaction() as session:
    repo = VoiceScriptRepository(session)
    script = repo.get_by_id(1)
    script.title = "更新"
    
    # save() は flush のみ実行、commit しない
    repo.save(script)
    
    # 追加の操作も同じトランザクション内
    script2 = repo.get_by_id(2)
    repo.remove(script2)  # これも flush のみ
    
    # with ブロック終了時に全ての変更が commit される
```

**適用場面**:
- 複数レコードの作成・更新・削除
- 複数テーブルにまたがる操作
- トランザクションの一貫性が重要な場合

---

### パターン 3: FastAPI Depends パターン

**特徴**:
- ✅ FastAPI の依存性注入を活用
- ✅ エンドポイント単位でセッション管理
- ✅ テストしやすい
- ⚠️ FastAPI 専用

**重要**: `get_db_session()` / `get_db_transaction()` は FastAPI Depends 専用です。
with 文で使用することは**できません**。with 文で使う場合は `_db_manager.get_sync_session()` を使用してください。

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from repom.database import get_db_session
from your_project.models import VoiceScript

router = APIRouter()

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

@router.get("/scripts/{script_id}")
def get_script(
    script_id: int,
    session: Session = Depends(get_db_session)
):
    repo = VoiceScriptRepository(session)
    return repo.get_by_id(script_id)
```

**適用場面**:
- FastAPI アプリケーション
- RESTful API エンドポイント
- テスタビリティが重要な場合

---

## 実装例

### 例1: シンプルな Repository（セッションなし）

```python
from repom import BaseRepository
from your_project.models import User

class UserRepository(BaseRepository[User]):
    """セッション管理を BaseRepository に任せる"""
    pass

# 使い方
repo = UserRepository()

# 読み取り
user = repo.get_by_id(1)
users = repo.get_by("email", "test@example.com")

# 作成
new_user = User(name="太郎", email="taro@example.com")
saved_user = repo.save(new_user)
```

---

### 例2: トランザクション制御が必要な Repository

```python
from repom import BaseRepository
from repom.database import get_db_transaction
from your_project.models import Order, OrderItem

class OrderRepository(BaseRepository[Order]):
    pass

class OrderItemRepository(BaseRepository[OrderItem]):
    pass

# 使い方（複数テーブルの操作を 1 トランザクションで）
def create_order_with_items(order_data: dict, items_data: list[dict]):
    from repom.database import _db_manager
    
    with _db_manager.get_sync_transaction() as session:
        order_repo = OrderRepository(session)
        item_repo = OrderItemRepository(session)
        
        # 注文作成
        order = order_repo.dict_save(order_data)
        
        # 注文明細作成
        for item_data in items_data:
            item_data["order_id"] = order.id
            item_repo.dict_save(item_data)
        
        # with ブロック終了時に自動コミット
        # エラー発生時は自動ロールバック
```

---

### 例3: FastAPI での Repository 使用

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from repom.database import get_db_session
from your_project.models import Task
from your_project.schemas import TaskCreate, TaskUpdate

router = APIRouter()

class TaskRepository(BaseRepository[Task]):
    pass

@router.post("/tasks")
def create_task(
    task_data: TaskCreate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.dict_save(task_data.model_dump())
    session.commit()  # 明示的にコミット
    return task

@router.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 更新
    for key, value in task_data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    
    session.commit()
    return task
```

---

## よくある間違い

### ❌ 間違い1: session=None で ValueError を raise

```python
# これは不要！
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            raise ValueError("session is required")  # ❌ 不要！
        super().__init__(VoiceScript, session)
```

**理由**: BaseRepository が `session=None` を自動的に処理します。エラーを raise すると、シンプルな使い方（パターン 1）ができなくなります。

---

### ❌ 間違い2: __init__ で get_db_session() を呼ぶ

```python
# これは避ける
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            session = get_db_session()  # ❌ ジェネレータなので期待通り動かない
        super().__init__(VoiceScript, session)
```

**理由**: `get_db_session()` はジェネレータなので、`next()` や `with` 文で使う必要があります。BaseRepository に任せるのが正解です。

---

### ❌ 間違い3: パターン 1 で複数操作を実行

```python
# これは危険
repo = VoiceScriptRepository()  # セッションなし

# 各操作が個別のセッションで実行される
user = repo.get_by_id(1)       # セッション 1
order = repo.get_by_id(2)      # セッション 2
order.user_id = user.id        # ❌ order は別セッションのオブジェクト
repo.save(order)               # エラー: DetachedInstanceError
```

**解決策**: 複数操作は `_db_manager.get_sync_transaction()` でラップする（パターン 2）

```python
# ✅ 正しい
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = VoiceScriptRepository(session)
    user = repo.get_by_id(1)
    order = repo.get_by_id(2)
    order.user_id = user.id
    repo.save(order)  # OK: 同じセッション
```

---

### ❌ 間違い4: get_db_session() を with 文で使おうとする

```python
# ❌ これは動作しません
with get_db_session() as session:  # TypeError: 'generator' object does not support the context manager protocol
    repo = TaskRepository(session)
    return repo.dict_save(data)
```

**理由**: `get_db_session()` / `get_db_transaction()` は FastAPI Depends 専用の generator 関数です。with 文では使用できません。

**正しい方法**:
```python
# ✅ with 文で使いたい場合
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:
    repo = TaskRepository(session)
    return repo.dict_save(data)

# ✅ FastAPI では Depends を使う
from fastapi import Depends
from repom.database import get_db_session

@router.post("/tasks")
def create_task(
    task_data: TaskCreate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.dict_save(task_data.model_dump())
    session.commit()
    return task
```

---

## パターン選択ガイド

| 状況 | 推奨パターン | 理由 |
|------|-------------|------|
| 単純な読み取り | パターン 1（セッションなし） | 最もシンプル |
| 単一レコードの作成・更新 | パターン 1（セッションなし） | コードが簡潔 |
| 複数レコードの操作 | パターン 2（明示的トランザクション） | アトミック性が保証される |
| 複数テーブルの操作 | パターン 2（明示的トランザクション） | トランザクションの一貫性 |
| FastAPI エンドポイント | パターン 3（Depends） | FastAPI の慣習に従う |
| CLI スクリプト | パターン 2（明示的トランザクション） | エラーハンドリングが明確 |
| バックグラウンドジョブ | パターン 2（明示的トランザクション） | トランザクション制御が重要 |

---

## トランザクション管理の詳細

### 内部セッション vs 外部セッション

repom の Repository は渡されたセッションの種類を自動判定し、適切な動作を選択します。

| セッションタイプ | 判定方法 | `save()` の動作 | `commit()` の責任 |
|----------------|---------|---------------|-----------------|
| **内部セッション** | `session=None` で初期化 | `flush()` + `commit()` | Repository |
| **外部セッション** | 明示的に渡される | `flush()` のみ | 呼び出し側 |

### 判定ロジック

```python
# BaseRepository / AsyncBaseRepository 内部の判定
using_internal_session = (
    self._session_override is None and 
    self._scoped_session is session
)

if using_internal_session:
    session.commit()  # 内部セッション: Repository が commit
else:
    session.flush()   # 外部セッション: 呼び出し側が commit
```

### 外部セッションの利点

1. **アトミック性**: 複数の Repository 操作を 1 トランザクションにまとめられる
2. **ロールバック制御**: エラー時の rollback を一箇所で管理
3. **パフォーマンス**: commit を最後にまとめることで DB アクセスを削減

### 実装例

```python
# 複数 Repository を 1 トランザクションで使用
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    user_repo = UserRepository(session)
    order_repo = OrderRepository(session)
    
    # ユーザー作成（flush のみ）
    user = user_repo.save(User(name="太郎"))
    
    # 注文作成（flush のみ）
    order = order_repo.save(Order(user_id=user.id, total=1000))
    
    # 全てまとめて commit（with ブロック終了時）
```

**注意事項**:
- 外部セッションでは `save()` が `flush()` のみ実行し、`refresh()` は実行しません
  * **同期版（BaseRepository）**: 内部セッション使用時のみ `refresh()` を実行
  * **非同期版（AsyncBaseRepository）**: 内部セッション使用時のみ `refresh()` を実行
- AutoDateTime などの DB 自動設定値を取得するには、明示的な `refresh()` が必要です
  ```python
  # 外部セッション使用時
  with _db_manager.get_sync_transaction() as session:
      repo = UserRepository(session)
      user = repo.save(User(name="太郎"))
      
      # created_at はまだ None（flush のみ実行）
      assert user.created_at is None
      
      # 明示的に refresh すれば取得可能
      session.refresh(user)
      assert user.created_at is not None
  ```
- エラー発生時、外部セッションでは Repository が rollback を実行せず、呼び出し側に委ねます
- 内部セッション使用時の動作は変更なし（後方互換性を維持）

---

## FastAPI 統合パターン

### FastAPI Depends の使い方

FastAPI の依存性注入システムと統合する場合、`get_async_db_session()` を使用します。

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session
from your_project.models import Article
from your_project.schemas import ArticleResponse, ArticleCreate

router = APIRouter()

@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    """記事を取得"""
    result = await session.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article.to_dict()

@router.post("/articles", response_model=ArticleResponse)
async def create_article(
    data: ArticleCreate,
    session: AsyncSession = Depends(get_async_db_session)
):
    """記事を作成"""
    article = Article(**data.dict())
    session.add(article)
    await session.flush()  # ID を取得
    return article.to_dict()
    # 自動で commit される
```

### FastAPI Users パターン

FastAPI Users は `AsyncGenerator[AsyncSession, None]` 型の依存関数を要求します。

```python
from fastapi import Depends, FastAPI
from fastapi_users import FastAPIUsers
from fastapi_users.db import SQLAlchemyUserDatabase
from repom.database import get_async_db_session
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()

# FastAPI Users のための依存関数
async def get_user_db(
    session: AsyncSession = Depends(get_async_db_session)
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)

# FastAPI Users の初期化
fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

# ルーター登録
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
```

### 実装の仕組みと使い分け

repom には **2種類のセッション取得方法** があります。

#### 1. FastAPI Depends 専用関数（generator）

```python
def get_db_session():
    """FastAPI Depends 専用 - with 文では使えません"""
    session = _db_manager.get_sync_session()
    try:
        yield session
    finally:
        session.close()

def get_db_transaction():
    """FastAPI Depends 専用 - with 文では使えません"""
    session = _db_manager.get_sync_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

**使い方**: FastAPI の `Depends()` でのみ使用
```python
from fastapi import Depends
from repom.database import get_db_session

@app.post("/items")
def create_item(
    data: ItemCreate,
    session: Session = Depends(get_db_session)  # ✅ OK
):
    item = Item(**data.dict())
    session.add(item)
    session.commit()
    return item
```

#### 2. DatabaseManager のメソッド（context manager）

```python
from repom.database import _db_manager

# with 文で使用する場合はこちら
with _db_manager.get_sync_session() as session:  # ✅ OK
    session.query(Model).all()

with _db_manager.get_sync_transaction() as session:  # ✅ OK
    session.add(item)
    # 自動コミット
```

**重要なポイント**:
- ❌ `get_db_session()` を with 文で使用することは**できません**
- ✅ with 文で使う場合は `_db_manager.get_sync_session()` を使用
- ✅ FastAPI では `Depends(get_db_session)` を使用
- ✅ CLI スクリプトでは `_db_manager.get_sync_transaction()` を使用

---

## トラブルシューティング

### TypeError: 'generator' object does not support the context manager protocol

**原因**: `get_db_session()` / `get_db_transaction()` を with 文で使おうとしています。

**問題のコード例**:
```python
# ❌ これは動作しません
from repom.database import get_db_session

with get_db_session() as session:
    # TypeError: 'generator' object does not support the context manager protocol
    session.execute(...)
```

**解決方法**:

**方法1: FastAPI では Depends を使う**（推奨）
```python
# ✅ FastAPI の場合
from fastapi import Depends
from sqlalchemy.orm import Session
from repom.database import get_db_session

@app.post("/items")
def create_item(
    data: ItemCreate,
    session: Session = Depends(get_db_session)  # ✅ OK
):
    session.execute(...)
    session.commit()
```

**方法2: with 文で使う場合は DatabaseManager を使う**:
```python
# ✅ CLI やスクリプトの場合
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:  # ✅ OK
    session.execute(...)

with _db_manager.get_sync_transaction() as session:  # ✅ OK（自動コミット）
    session.execute(...)
```

**技術的な背景**:
- `get_db_session()` は純粋な generator 関数（FastAPI Depends 専用）
- generator は context manager プロトコルをサポートしていない
- with 文で使う場合は `_db_manager` のメソッドを使用する必要がある

### TypeError: object AsyncSession can't be used in 'await' expression

**原因**: `get_async_session()` の戻り値を誤って await しています。

**間違った例**:
```python
session = await get_async_session()  # ❌ この時点で既に AsyncSession
```

**正しい例**:
```python
session = await get_async_session()  # ✅ get_async_session() 自体が async 関数
await session.execute(...)           # ✅ execute を await
```

### ImportError: cannot import name 'AsyncSession'

**原因**: 非同期ドライバがインストールされていません。

**解決方法**:
```bash
poetry add aiosqlite  # SQLite の場合
poetry add asyncpg    # PostgreSQL の場合
```

### RuntimeError: Event loop is closed

**原因**: pytest-asyncio の設定が不足しています。

**解決方法**:
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 非同期版のセッション管理パターン

### AsyncBaseRepository のセッション管理

非同期版の `AsyncBaseRepository` も同様に `session=None` を許容し、柔軟なセッション管理が可能です。

### 非同期パターン 1: FastAPI での使用（推奨）

**特徴**:
- ✅ `lifespan_context()` で自動的にエンジンをクリーンアップ
- ✅ `Depends` パターンでシンプルに統合
- ✅ `dispose_async()` の手動呼び出し不要

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session, get_lifespan_manager
from repom.async_base_repository import AsyncBaseRepository
from your_project.models import Task

# lifespan で自動クリーンアップ
app = FastAPI(lifespan=get_lifespan_manager())

@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    return task
```

**ポイント**:
- `lifespan=get_lifespan_manager()` が shutdown 時に自動的に `dispose_all()` を呼ぶ
- エンジンのクリーンアップを気にする必要なし

---

### 非同期パターン 2: スタンドアロンスクリプト（CLI、バッチ、Jupyter）

**特徴**:
- ✅ 自動的に `dispose_async()` を呼ぶ
- ✅ プログラムが正常に終了する
- ✅ CLI ツール、バッチスクリプトに最適

**❌ よくある問題**:

```python
# ❌ これはプログラムが終了しない
import asyncio
from repom.database import _db_manager

async def main():
    async with _db_manager.get_async_transaction() as session:
        # データベース操作
        pass
    # ここで終了するはずだが、プログラムが停止しない

if __name__ == "__main__":
    asyncio.run(main())  # ハングする
```

**理由**: SQLAlchemy の非同期エンジンは接続プールとバックグラウンドタスクを保持し続けるため、明示的に `dispose_async()` を呼ばないと終了しません。

**✅ 解決方法1: `get_standalone_async_transaction()` を使う**（推奨）:

```python
import asyncio
from repom.database import get_standalone_async_transaction
from sqlalchemy import select
from your_project.models import Task

async def main():
    async with get_standalone_async_transaction() as session:
        # データベース操作
        result = await session.execute(select(Task).limit(10))
        tasks = result.scalars().all()
        for task in tasks:
            print(task.title)
    # 自動的に dispose_async() が呼ばれる

if __name__ == "__main__":
    asyncio.run(main())
```

**✅ 解決方法2: 手動で `dispose_async()` を呼ぶ**:

```python
import asyncio
from repom.database import _db_manager

async def main():
    try:
        async with _db_manager.get_async_transaction() as session:
            # データベース操作
            pass
    finally:
        # 接続プールをクリーンアップ（必須！）
        await _db_manager.dispose_async()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 非同期パターンの選択ガイド

| ユースケース | 推奨パターン | クリーンアップ |
|-------------|-------------|---------------|
| **FastAPI アプリ** | `get_async_db_session()` + `lifespan` | 自動 |
| **CLI ツール** | `get_standalone_async_transaction()` | 自動 |
| **バッチスクリプト** | `get_standalone_async_transaction()` | 自動 |
| **Jupyter Notebook** | `get_standalone_async_transaction()` | 自動 |
| **pytest での非同期テスト** | fixture + `dispose_async()` | fixture で管理 |

---

### 非同期版のベストプラクティス

#### ✅ DO: FastAPI では lifespan を使う

```python
# Good: lifespan が自動的にクリーンアップ
from fastapi import FastAPI
from repom.database import get_lifespan_manager

app = FastAPI(lifespan=get_lifespan_manager())
```

#### ✅ DO: スタンドアロンスクリプトでは専用ヘルパーを使う

```python
# Good: 自動的に dispose される
import asyncio
from repom.database import get_standalone_async_transaction

async def main():
    async with get_standalone_async_transaction() as session:
        # 処理

asyncio.run(main())
```

#### ❌ DON'T: スタンドアロンで dispose を忘れる

```python
# Bad: プログラムが終了しない
async with _db_manager.get_async_transaction() as session:
    pass
# dispose_async() を呼んでいない
```

---

## まとめ

**覚えておくべき3つのポイント**:

1. **`session=None` は OK** - BaseRepository が自動的に処理します
2. **シンプルな操作はパターン 1** - セッションを渡さず、そのまま使う
3. **複数操作はパターン 2** - `get_db_transaction()` でラップする

**基本ルール（同期版）**:
- 単純な操作 → セッションなし
- 複雑な操作 → 明示的トランザクション
- FastAPI → Depends パターン

**基本ルール（非同期版）**:
- FastAPI → `get_async_db_session()` + `lifespan_context()`
- CLI/バッチ → `get_standalone_async_transaction()`
- 手動管理 → `get_async_transaction()` + `dispose_async()`

**避けるべきこと**:
- ❌ Repository の `__init__` で `session is None` チェックして raise
- ❌ `__init__` で `get_db_session()` を直接呼ぶ
- ❌ パターン 1 で複数操作を実行
- ❌ スタンドアロンスクリプトで `dispose_async()` を忘れる

---

## 関連ドキュメント

- [repository_and_utilities_guide.md](repository_and_utilities_guide.md) - BaseRepository の基本的な使い方
- [async_repository_guide.md](async_repository_guide.md) - 非同期版 Repository の使い方
