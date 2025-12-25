# Repository セッション管理パターンガイド

**目的**: BaseRepository でのセッション管理の仕組みと推奨パターンを理解する

**対象読者**: repom を使ってリポジトリパターンを実装する開発者・AI エージェント

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
from repom.base_repository import BaseRepository
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
- ✅ エラー時の自動ロールバック
- ✅ トランザクション制御が明確
- ⚠️ やや冗長（with 文が必要）

```python
from repom.database import get_db_transaction
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 使い方
with get_db_transaction() as session:
    repo = VoiceScriptRepository(session)
    script = repo.get_by_id(1)
    script.title = "更新"
    repo.save(script)
    # with ブロック終了時に自動コミット
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

### 例 1: シンプルな Repository（セッションなし）

```python
from repom.base_repository import BaseRepository
from your_project.models import User

class UserRepository(BaseRepository[User]):
    """セッション管理は BaseRepository に任せる"""
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

### 例 2: トランザクション制御が必要な Repository

```python
from repom.base_repository import BaseRepository
from repom.database import get_db_transaction
from your_project.models import Order, OrderItem

class OrderRepository(BaseRepository[Order]):
    pass

class OrderItemRepository(BaseRepository[OrderItem]):
    pass

# 使い方：複数テーブルの操作を 1 トランザクションで
def create_order_with_items(order_data: dict, items_data: list[dict]):
    with get_db_transaction() as session:
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

### 例 3: FastAPI での Repository 使用

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

### ❌ 間違い 1: session=None で ValueError を raise

```python
# これは不要！
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            raise ValueError("session is required")  # ❌ 不要
        super().__init__(VoiceScript, session)
```

**理由**: BaseRepository が `session=None` を自動的に処理します。エラーを raise すると、シンプルな使い方（パターン 1）ができなくなります。

---

### ❌ 間違い 2: __init__ で get_db_session() を呼ぶ

```python
# これは避ける！
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            session = get_db_session()  # ❌ ジェネレータなので期待通り動かない
        super().__init__(VoiceScript, session)
```

**理由**: `get_db_session()` はジェネレータなので、`next()` や `with` 文で使う必要があります。BaseRepository に任せるのが正解です。

---

### ❌ 間違い 3: パターン 1 で複数操作を実行

```python
# これは危険！
repo = VoiceScriptRepository()  # セッションなし

# 各操作が個別のセッションで実行される
user = repo.get_by_id(1)       # セッション 1
order = repo.get_by_id(2)      # セッション 2
order.user_id = user.id        # ❌ order は別セッションのオブジェクト
repo.save(order)               # エラー: DetachedInstanceError
```

**解決策**: 複数操作は `get_db_transaction()` でラップする（パターン 2）

```python
# ✅ 正しい
with get_db_transaction() as session:
    repo = VoiceScriptRepository(session)
    user = repo.get_by_id(1)
    order = repo.get_by_id(2)
    order.user_id = user.id
    repo.save(order)  # OK: 同じセッション
```

---

### ❌ 間違い 4: FastAPI で get_db_transaction() を使う

```python
# これは avoid！
@router.post("/tasks")
def create_task(task_data: TaskCreate):
    with get_db_transaction() as session:  # ⚠️ FastAPI では Depends を推奨
        repo = TaskRepository(session)
        return repo.dict_save(task_data.model_dump())
```

**理由**: FastAPI では依存性注入（Depends）を使うのが慣習です。テストもしやすくなります。

**推奨**:
```python
# ✅ FastAPI では Depends を使う
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

## FastAPI 統合パターン

### FastAPI Depends の使い方

FastAPI の依存性注入システムと統合する場合、`get_async_db_session()` を使用します：

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

FastAPI Users は `AsyncGenerator[AsyncSession, None]` 型の依存関数を要求します：

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

---

## トラブルシューティング

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

**原因**: 非同期ドライバーがインストールされていません。

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

## まとめ

**覚えておくべき 3 つのポイント**:

1. **`session=None` は OK** - BaseRepository が自動的に処理します
2. **シンプルな操作はパターン 1** - セッションを渡さず、そのまま使う
3. **複数操作はパターン 2** - `get_db_transaction()` でラップする

**基本ルール**:
- 単純な操作 → セッションなし
- 複雑な操作 → 明示的トランザクション
- FastAPI → Depends パターン

**避けるべきこと**:
- ❌ Repository の `__init__` で `session is None` チェックして raise
- ❌ `__init__` で `get_db_session()` を直接呼ぶ
- ❌ パターン 1 で複数操作を実行

---

## 関連ドキュメント

- [repository_and_utilities_guide.md](repository_and_utilities_guide.md) - BaseRepository の基本的な使い方
- [../database/migration_to_database_py.md](../database/migration_to_database_py.md) - database.py への移行ガイド
- [async_repository_guide.md](async_repository_guide.md) - 非同期版 Repository の使い方
