# Repository セチE��ョン管琁E��ターンガイチE

**目皁E*: BaseRepository でのセチE��ョン管琁E�E仕絁E��と推奨パターンを理解する

**対象読老E*: repom を使ってリポジトリパターンを実裁E��る開発老E�EAI エージェンチE

---

## 📚 目次

1. [概要](#概要E
2. [BaseRepository のセチE��ョン管琁E�E仕絁E��](#baserepository-のセチE��ョン管琁E�E仕絁E��)
3. [推奨パターン](#推奨パターン)
4. [実裁E��](#実裁E��E
5. [よくある間違い](#よくある間違ぁE
6. [パターン選択ガイド](#パターン選択ガイチE

---

## 概要E

`BaseRepository` は **`session=None` を許容** し、セチE��ョンが提供されてぁE��ぁE��合�E自動的に `get_db_session()` を使用します。これにより、シンプルな使ぁE��から高度なトランザクション制御まで、柔軟な実裁E��可能です、E

**重要E*: Repository の `__init__` で `session is None` をチェチE��して `ValueError` めEraise する忁E���E **ありません**、EaseRepository が�E動的に処琁E��ます、E

---

## BaseRepository のセチE��ョン管琁E�E仕絁E��

### 冁E��実裁E

```python
class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: Optional[Session] = None):
        self.model = model
        self.session = session  # None でめEOK

    def get_by_id(self, id: int) -> Optional[T]:
        # session ぁENone の場合、get_db_session() を使用
        if self.session is None:
            with get_db_session() as session:
                return session.query(self.model).filter_by(id=id).first()
        else:
            # 渡されたセチE��ョンを使用
            return self.session.query(self.model).filter_by(id=id).first()
```

**ポインチE*:
- `session=None` でインスタンス化可能
- 吁E��ソチE��で `self.session is None` をチェチE��
- None の場合�E `get_db_session()` で自動セチE��ョン作�E
- 提供されてぁE��場合�Eそれを使用

---

## 推奨パターン

### パターン 1: セチE��ョンなし（最もシンプル�E�E

**特徴**:
- ✁Eコードが最もシンプル
- ✁E単純な CRUD 操作に最適
- ❁Eトランザクション制御なし（各操作が個別コミット！E
- ❁E褁E��操作をアトミチE��にできなぁE

```python
from repom import BaseRepository
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 使ぁE��
repo = VoiceScriptRepository()
script = repo.get_by_id(1)
scripts = repo.get_all()
```

**適用場面**:
- 読み取り専用の操佁E
- 単一レコード�E作�E・更新・削除
- トランザクション制御が不要な場吁E

---

### パターン 2: 明示皁E��ランザクション�E�推奨�E�E

**特徴**:
- ✁E褁E��操作をアトミチE��に実行可能
- ✁Eエラー時�E自動ロールバック
- ✁Eトランザクション制御が�E確
- ⚠�E�EめE��冗長�E�Eith 斁E��忁E��E��E

**重要な動佁E*:
- 外部セチE��ョンを渡した場合、Repository の `save()` / `saves()` / `remove()` は `commit()` を実行しません
- 代わりに `flush()` のみが実行され、変更はトランザクション冁E��保留されまぁE
- `commit()` は `with` ブロチE��終亁E���E�また�E明示皁E��呼び出し）まで実行されません

```python
from repom.database import _db_manager
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 使ぁE��
with _db_manager.get_sync_transaction() as session:
    repo = VoiceScriptRepository(session)
    script = repo.get_by_id(1)
    script.title = "更新"
    
    # save() は flush のみ実行！Eommit しなぁE��E
    repo.save(script)
    
    # 追加の操作も同じトランザクション冁E
    script2 = repo.get_by_id(2)
    repo.remove(script2)  # これめEflush のみ
    
    # with ブロチE��終亁E��に全ての変更ぁEcommit されめE
```

**適用場面**:
- 褁E��レコード�E作�E・更新・削除
- 褁E��チE�Eブルにまたがる操佁E
- トランザクションの一貫性が重要な場吁E

---

### パターン 3: FastAPI Depends パターン

**特徴**:
- ✁EFastAPI の依存性注入を活用
- ✁Eエンド�Eイント単位でセチE��ョン管琁E
- ✁EチE��トしめE��ぁE
- ⚠�E�EFastAPI 専用

**重要E*: `get_db_session()` / `get_db_transaction()` は FastAPI Depends 専用です、E
with 斁E��使用することは**できません**。with 斁E��使ぁE��合�E `_db_manager.get_sync_session()` を使用してください、E

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
- RESTful API エンド�EインチE
- チE��タビリチE��が重要な場吁E

---

## 実裁E��E

### 侁E1: シンプルな Repository�E�セチE��ョンなし！E

```python
from repom import BaseRepository
from your_project.models import User

class UserRepository(BaseRepository[User]):
    """セチE��ョン管琁E�E BaseRepository に任せる"""
    pass

# 使ぁE��
repo = UserRepository()

# 読み取り
user = repo.get_by_id(1)
users = repo.get_by("email", "test@example.com")

# 作�E
new_user = User(name="太郁E, email="taro@example.com")
saved_user = repo.save(new_user)
```

---

### 侁E2: トランザクション制御が忁E��な Repository

```python
from repom import BaseRepository
from repom.database import get_db_transaction
from your_project.models import Order, OrderItem

class OrderRepository(BaseRepository[Order]):
    pass

class OrderItemRepository(BaseRepository[OrderItem]):
    pass

# 使ぁE���E�褁E��チE�Eブルの操作を 1 トランザクションで
def create_order_with_items(order_data: dict, items_data: list[dict]):
    from repom.database import _db_manager
    
    with _db_manager.get_sync_transaction() as session:
        order_repo = OrderRepository(session)
        item_repo = OrderItemRepository(session)
        
        # 注斁E���E
        order = order_repo.dict_save(order_data)
        
        # 注斁E�E細作�E
        for item_data in items_data:
            item_data["order_id"] = order.id
            item_repo.dict_save(item_data)
        
        # with ブロチE��終亁E��に自動コミッチE
        # エラー発生時は自動ロールバック
```

---

### 侁E3: FastAPI での Repository 使用

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
    session.commit()  # 明示皁E��コミッチE
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

## よくある間違ぁE

### ❁E間違ぁE1: session=None で ValueError めEraise

```python
# これは不要E��E
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            raise ValueError("session is required")  # ❁E不要E
        super().__init__(VoiceScript, session)
```

**琁E��**: BaseRepository ぁE`session=None` を�E動的に処琁E��ます。エラーめEraise すると、シンプルな使ぁE���E�パターン 1�E�ができなくなります、E

---

### ❁E間違ぁE2: __init__ で get_db_session() を呼ぶ

```python
# これは避ける�E�E
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            session = get_db_session()  # ❁Eジェネレータなので期征E��り動かなぁE
        super().__init__(VoiceScript, session)
```

**琁E��**: `get_db_session()` はジェネレータなので、`next()` めE`with` 斁E��使ぁE��E��があります、EaseRepository に任せるのが正解です、E

---

### ❁E間違ぁE3: パターン 1 で褁E��操作を実衁E

```python
# これは危険�E�E
repo = VoiceScriptRepository()  # セチE��ョンなぁE

# 吁E��作が個別のセチE��ョンで実行される
user = repo.get_by_id(1)       # セチE��ョン 1
order = repo.get_by_id(2)      # セチE��ョン 2
order.user_id = user.id        # ❁Eorder は別セチE��ョンのオブジェクチE
repo.save(order)               # エラー: DetachedInstanceError
```

**解決筁E*: 褁E��操作�E `_db_manager.get_sync_transaction()` でラチE�Eする�E�パターン 2�E�E

```python
# ✁E正しい
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = VoiceScriptRepository(session)
    user = repo.get_by_id(1)
    order = repo.get_by_id(2)
    order.user_id = user.id
    repo.save(order)  # OK: 同じセチE��ョン
```

---

### ❁E間違ぁE4: get_db_session() めEwith 斁E��使おうとする

```python
# ❁Eこれは動作しません�E�E
with get_db_session() as session:  # TypeError: 'generator' object does not support the context manager protocol
    repo = TaskRepository(session)
    return repo.dict_save(data)
```

**琁E��**: `get_db_session()` / `get_db_transaction()` は FastAPI Depends 専用の generator 関数です。with 斁E��は使用できません、E

**正しい方況E*:
```python
# ✁Ewith 斁E��使ぁE��ぁE��吁E
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:
    repo = TaskRepository(session)
    return repo.dict_save(data)

# ✁EFastAPI では Depends を使ぁE
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

**推奨**:
```python
# ✁EFastAPI では Depends を使ぁE
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

## パターン選択ガイチE

| 状況E| 推奨パターン | 琁E�� |
|------|-------------|------|
| 単純な読み取り | パターン 1�E�セチE��ョンなし！E| 最もシンプル |
| 単一レコード�E作�E・更新 | パターン 1�E�セチE��ョンなし！E| コードが簡潁E|
| 褁E��レコード�E操佁E| パターン 2�E��E示皁E��ランザクション�E�E| アトミチE��性が保証されめE|
| 褁E��チE�Eブルの操佁E| パターン 2�E��E示皁E��ランザクション�E�E| トランザクションの一貫性 |
| FastAPI エンド�EインチE| パターン 3�E�Eepends�E�E| FastAPI の慣習に従う |
| CLI スクリプト | パターン 2�E��E示皁E��ランザクション�E�E| エラーハンドリングが�E確 |
| バックグラウンドジョチE| パターン 2�E��E示皁E��ランザクション�E�E| トランザクション制御が重要E|

---

## トランザクション管琁E�E詳細

### 冁E��セチE��ョン vs 外部セチE��ョン

repom の Repository は渡されたセチE��ョンの種類を自動判定し、E��刁E��動作を選択します！E

| セチE��ョンタイチE| 判定方況E| `save()` の動佁E| `commit()` の責任 |
|----------------|---------|---------------|-----------------|
| **冁E��セチE��ョン** | `session=None` で初期匁E| `flush()` + `commit()` | Repository |
| **外部セチE��ョン** | 明示皁E��渡されめE| `flush()` のみ | 呼び出し�E |

### 判定ロジチE��

```python
# BaseRepository / AsyncBaseRepository 冁E��の判宁E
using_internal_session = (
    self._session_override is None and 
    self._scoped_session is session
)

if using_internal_session:
    session.commit()  # 冁E��セチE��ョン: Repository ぁEcommit
else:
    session.flush()   # 外部セチE��ョン: 呼び出し�EぁEcommit
```

### 外部セチE��ョンの利点

1. **アトミチE��性**: 褁E��の Repository 操作を 1 トランザクションにまとめられる
2. **ロールバック制御**: エラー時�E rollback を一箁E��で管琁E
3. **パフォーマンス**: commit を最後にまとめることで DB アクセスを削渁E

### 実裁E��E

```python
# 褁E�� Repository めE1 トランザクションで使用
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    user_repo = UserRepository(session)
    order_repo = OrderRepository(session)
    
    # ユーザー作�E�E�Elush のみ�E�E
    user = user_repo.save(User(name="太郁E))
    
    # 注斁E���E�E�Elush のみ�E�E
    order = order_repo.save(Order(user_id=user.id, total=1000))
    
    # 全てまとめて commit�E�Eith ブロチE��終亁E���E�E
```

**注意事頁E*:
- 外部セチE��ョンでは `save()` ぁE`flush()` のみ実行し、`refresh()` は実行しません
  * **同期版！EaseRepository�E�E*: 冁E��セチE��ョン使用時�Eみ `refresh()` を実衁E
  * **非同期版�E�EsyncBaseRepository�E�E*: 冁E��セチE��ョン使用時�Eみ `refresh()` を実衁E
- AutoDateTime などの DB 自動設定値を取得するには、�E示皁E�� `refresh()` が忁E��でぁE
  ```python
  # 外部セチE��ョン使用晁E
  with _db_manager.get_sync_transaction() as session:
      repo = UserRepository(session)
      user = repo.save(User(name="太郁E))
      
      # created_at はまだ None�E�Elush のみ実行！E
      assert user.created_at is None
      
      # 明示皁E�� refresh すれば取得可能
      session.refresh(user)
      assert user.created_at is not None
  ```
- エラー発生時、外部セチE��ョンでは Repository ぁErollback を実行せず、呼び出し�Eに委�EまぁE
- 冁E��セチE��ョン使用時�E動作�E変更なし（後方互換性を維持E��E

---

## FastAPI 統合パターン

### FastAPI Depends の使ぁE��

FastAPI の依存性注入シスチE��と統合する場合、`get_async_db_session()` を使用します！E

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
    """記事を取征E""
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
    """記事を作�E"""
    article = Article(**data.dict())
    session.add(article)
    await session.flush()  # ID を取征E
    return article.to_dict()
    # 自動で commit されめE
```

### FastAPI Users パターン

FastAPI Users は `AsyncGenerator[AsyncSession, None]` 型�E依存関数を要求します！E

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

# FastAPI Users の初期匁E
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

### 実裁E�E仕絁E��と使ぁE�EぁE

repom には **2種類�EセチE��ョン取得方況E* があります！E

#### 1. FastAPI Depends 専用関数�E�Eenerator�E�E

```python
def get_db_session():
    """FastAPI Depends 専用 - with 斁E��は使えません"""
    session = _db_manager.get_sync_session()
    try:
        yield session
    finally:
        session.close()

def get_db_transaction():
    """FastAPI Depends 専用 - with 斁E��は使えません"""
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

**使ぁE��**: FastAPI の `Depends()` でのみ使用
```python
from fastapi import Depends
from repom.database import get_db_session

@app.post("/items")
def create_item(
    data: ItemCreate,
    session: Session = Depends(get_db_session)  # ✁EOK
):
    item = Item(**data.dict())
    session.add(item)
    session.commit()
    return item
```

#### 2. DatabaseManager のメソチE���E�Eontext manager�E�E

```python
from repom.database import _db_manager

# with 斁E��使用する場合�EこちめE
with _db_manager.get_sync_session() as session:  # ✁EOK
    session.query(Model).all()

with _db_manager.get_sync_transaction() as session:  # ✁EOK
    session.add(item)
    # 自動コミッチE
```

**重要�EインチE*:
- ❁E`get_db_session()` めEwith 斁E��使用することは**できません**
- ✁Ewith 斁E��使ぁE��ぁE��合�E `_db_manager.get_sync_session()` を使用
- ✁EFastAPI では `Depends(get_db_session)` を使用
- ✁ECLI スクリプトでは `_db_manager.get_sync_transaction()` を使用

---

## トラブルシューチE��ング

### TypeError: 'generator' object does not support the context manager protocol

**原因**: `get_db_session()` / `get_db_transaction()` めEwith 斁E��使おうとしてぁE��す、E

**問題�Eコード侁E*:
```python
# ❁Eこれは動作しません
from repom.database import get_db_session

with get_db_session() as session:
    # TypeError: 'generator' object does not support the context manager protocol
    session.execute(...)
```

**解決方況E*:

**方況E1: FastAPI では Depends を使ぁE*�E�推奨�E�E
```python
# ✁EFastAPI の場吁E
from fastapi import Depends
from sqlalchemy.orm import Session
from repom.database import get_db_session

@app.post("/items")
def create_item(
    data: ItemCreate,
    session: Session = Depends(get_db_session)  # ✁EOK
):
    session.execute(...)
    session.commit()
```

**方況E2: with 斁E��使ぁE��合�E DatabaseManager を使ぁE*:
```python
# ✁ECLI めE��クリプトの場吁E
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:  # ✁EOK
    session.execute(...)

with _db_manager.get_sync_transaction() as session:  # ✁EOK�E��E動コミット！E
    session.execute(...)
```

**技術的な背景**:
- `get_db_session()` は純粋な generator 関数�E�EastAPI Depends 専用�E�E
- generator は context manager プロトコルをサポ�EトしてぁE��ぁE
- with 斁E��使ぁE��合�E `_db_manager` のメソチE��を使用する忁E��がある

### TypeError: object AsyncSession can't be used in 'await' expression

**原因**: `get_async_session()` の戻り値を誤って await してぁE��す、E

**間違った侁E*:
```python
session = await get_async_session()  # ❁Eこ�E時点で既に AsyncSession
```

**正しい侁E*:
```python
session = await get_async_session()  # ✁Eget_async_session() 自体が async 関数
await session.execute(...)           # ✁Eexecute めEawait
```

### ImportError: cannot import name 'AsyncSession'

**原因**: 非同期ドライバ�Eがインスト�EルされてぁE��せん、E

**解決方況E*:
```bash
poetry add aiosqlite  # SQLite の場吁E
poetry add asyncpg    # PostgreSQL の場吁E
```

### RuntimeError: Event loop is closed

**原因**: pytest-asyncio の設定が不足してぁE��す、E

**解決方況E*:
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 非同期版のセチE��ョン管琁E��ターン

### AsyncBaseRepository のセチE��ョン管琁E

非同期版の `AsyncBaseRepository` も同様に `session=None` を許容し、柔軟なセチE��ョン管琁E��可能です、E

### 非同期パターン 1: FastAPI での使用�E�推奨�E�E

**特徴**:
- ✁E`lifespan_context()` で自動的にエンジンをクリーンアチE�E
- ✁E`Depends` パターンでシンプルに統吁E
- ✁E`dispose_async()` の手動呼び出し不要E

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session, get_lifespan_manager
from repom.async_base_repository import AsyncBaseRepository
from your_project.models import Task

# lifespan で自動クリーンアチE�E
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

**ポインチE*:
- `lifespan=get_lifespan_manager()` ぁEshutdown 時に自動的に `dispose_all()` を呼ぶ
- エンジンのクリーンアチE�Eを気にする忁E��なぁE

---

### 非同期パターン 2: スタンドアロンスクリプト�E�ELI、バチE��、Jupyter�E�E

**特徴**:
- ✁E自動的に `dispose_async()` を呼ぶ
- ✁Eプログラムが正常に終亁E��めE
- ✁ECLI チE�Eル、バチE��スクリプトに最適

**❁Eよくある問顁E*:

```python
# ❁Eこれはプログラムが終亁E��なぁE
import asyncio
from repom.database import _db_manager

async def main():
    async with _db_manager.get_async_transaction() as session:
        # チE�Eタベ�Eス操佁E
        pass
    # ここで終亁E��る�Eずだが、�Eログラムが停止しなぁE

if __name__ == "__main__":
    asyncio.run(main())  # ハングする
```

**琁E��**: SQLAlchemy の非同期エンジンは接続�Eールとバックグラウンドタスクを保持し続けるため、�E示皁E�� `dispose_async()` を呼ばなぁE��終亁E��ません、E

**✁E解決方況E1: `get_standalone_async_transaction()` を使ぁE��推奨�E�E*:

```python
import asyncio
from repom.database import get_standalone_async_transaction
from sqlalchemy import select
from your_project.models import Task

async def main():
    async with get_standalone_async_transaction() as session:
        # チE�Eタベ�Eス操佁E
        result = await session.execute(select(Task).limit(10))
        tasks = result.scalars().all()
        for task in tasks:
            print(task.title)
    # 自動的に dispose_async() が呼ばれる

if __name__ == "__main__":
    asyncio.run(main())
```

**✁E解決方況E2: 手動で `dispose_async()` を呼ぶ**:

```python
import asyncio
from repom.database import _db_manager

async def main():
    try:
        async with _db_manager.get_async_transaction() as session:
            # チE�Eタベ�Eス操佁E
            pass
    finally:
        # 接続�EールをクリーンアチE�E�E�忁E��！E��E
        await _db_manager.dispose_async()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 非同期パターンの選択ガイチE

| ユースケース | 推奨パターン | クリーンアチE�E |
|-------------|-------------|---------------|
| **FastAPI アプリ** | `get_async_db_session()` + `lifespan` | 自勁E|
| **CLI チE�Eル** | `get_standalone_async_transaction()` | 自勁E|
| **バッチスクリプト** | `get_standalone_async_transaction()` | 自勁E|
| **Jupyter Notebook** | `get_standalone_async_transaction()` | 自勁E|
| **pytest での非同期テスチE* | fixture + `dispose_async()` | fixture で管琁E|

---

### 非同期版のベスト�EラクチE��ス

#### ✁EDO: FastAPI では lifespan を使ぁE

```python
# Good: lifespan が�E動的にクリーンアチE�E
from fastapi import FastAPI
from repom.database import get_lifespan_manager

app = FastAPI(lifespan=get_lifespan_manager())
```

#### ✁EDO: スタンドアロンスクリプトでは専用ヘルパ�Eを使ぁE

```python
# Good: 自動的に dispose されめE
import asyncio
from repom.database import get_standalone_async_transaction

async def main():
    async with get_standalone_async_transaction() as session:
        # 処琁E

asyncio.run(main())
```

#### ❁EDON'T: スタンドアロンで dispose を忘れめE

```python
# Bad: プログラムが終亁E��なぁE
async with _db_manager.get_async_transaction() as session:
    pass
# dispose_async() を呼んでぁE��ぁE
```

---

## まとめE

**覚えておくべぁE3 つのポインチE*:

1. **`session=None` は OK** - BaseRepository が�E動的に処琁E��まぁE
2. **シンプルな操作�Eパターン 1** - セチE��ョンを渡さず、そのまま使ぁE
3. **褁E��操作�Eパターン 2** - `get_db_transaction()` でラチE�Eする

**基本ルール�E�同期版�E�E*:
- 単純な操佁EↁEセチE��ョンなぁE
- 褁E��な操佁EↁE明示皁E��ランザクション
- FastAPI ↁEDepends パターン

**基本ルール�E�非同期版！E*:
- FastAPI ↁE`get_async_db_session()` + `lifespan_context()`
- CLI/バッチEↁE`get_standalone_async_transaction()`
- 手動管琁EↁE`get_async_transaction()` + `dispose_async()`

**避けるべきこと**:
- ❁ERepository の `__init__` で `session is None` チェチE��して raise
- ❁E`__init__` で `get_db_session()` を直接呼ぶ
- ❁Eパターン 1 で褁E��操作を実衁E
- ❁Eスタンドアロンスクリプトで `dispose_async()` を忘れめE

---

## 関連ドキュメンチE

- [repository_and_utilities_guide.md](repository_and_utilities_guide.md) - BaseRepository の基本皁E��使ぁE��
- [async_repository_guide.md](async_repository_guide.md) - 非同期版 Repository の使ぁE��
