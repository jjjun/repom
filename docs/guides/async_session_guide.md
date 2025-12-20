# 非同期セッション（AsyncSession）サポートガイド

## 📖 概要

repom は FastAPI Users などの非同期フレームワークとの統合を想定し、AsyncSession をフルサポートしています。
同期セッションと非同期セッションの両方が利用可能で、プロジェクトの要件に応じて選択できます。

### なぜ AsyncSession が必要なのか？

- **FastAPI Users**: FastAPI Users は非同期データベース操作を前提とした認証ライブラリです
- **パフォーマンス**: I/O バウンドな操作で並行処理が可能になります
- **モダンな Python**: async/await は Python の標準的な非同期処理パターンです

### ハイブリッドアプローチ

repom は**同期セッションと非同期セッションの両方**をサポートします：

- **同期セッション** (`repom.session`): 既存のコード、CLI ツール、シンプルなアプリケーション向け
- **非同期セッション** (`repom.async_session`): FastAPI、FastAPI Users、高スループットアプリケーション向け

両方の API が共存し、プロジェクトの要件に応じて使い分けができます。

---

## 🚀 インストール

### 必須依存関係のインストール

非同期セッション機能を使用するには、非同期データベースドライバーをインストールする必要があります。

#### SQLite の場合（推奨）

```bash
# repom に aiosqlite をインストール
cd repom
poetry add aiosqlite

# または既存プロジェクトから使用する場合
poetry add repom[async]
```

#### PostgreSQL の場合

```bash
poetry add repom[async-all]
# これにより aiosqlite と asyncpg の両方がインストールされます
```

---

## 📚 基本的な使い方

### 1. AsyncSession の作成と手動管理

手動でセッションを開閉する場合は `get_async_session()` を使用します。

```python
from repom.async_session import get_async_session
from sqlalchemy import select
from your_project.models import User

async def get_user_by_id(user_id: int):
    """AsyncSession を手動で管理"""
    session = await get_async_session()
    try:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        return user
    finally:
        await session.close()  # 必ず close すること
```

**注意**: `get_async_session()` は手動で `close()` する必要があります。

---

### 2. AsyncSession の自動管理（推奨）

トランザクション自動管理が必要な場合は `get_async_db_session()` を使用します。

```python
from repom.async_session import get_async_db_session
from sqlalchemy import select
from your_project.models import User

async def create_user(email: str, name: str):
    """トランザクションを自動管理"""
    async for session in get_async_db_session():
        user = User(email=email, name=name)
        session.add(user)
        # ここで return すると自動で commit される
        return user
    # エラーが発生すると自動で rollback される
```

**メリット**:
- ✅ 自動 `commit`（成功時）
- ✅ 自動 `rollback`（エラー時）
- ✅ 自動 `close`（常に）
- ✅ コードがシンプル

---

## 🔧 FastAPI 統合

### FastAPI Users パターン

FastAPI Users は `AsyncGenerator[AsyncSession, None]` 型の依存関数を要求します。

```python
from fastapi import Depends, FastAPI
from fastapi_users import FastAPIUsers
from fastapi_users.db import SQLAlchemyUserDatabase
from repom.async_session import get_async_db_session
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

### FastAPI エンドポイント例

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from repom.async_session import get_async_db_session
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

---

## 🧪 テストでの使用

repom は非同期テスト用のフィクスチャを提供しています。

### テストフィクスチャのセットアップ

```python
# tests/conftest.py
import pytest
from repom.testing import create_async_test_fixtures

# AsyncSession テストフィクスチャを作成
async_db_engine, async_db_test = create_async_test_fixtures()
```

### テストの作成

```python
import pytest
from sqlalchemy import select
from your_project.models import User

@pytest.mark.asyncio
async def test_create_user(async_db_test):
    """ユーザー作成テスト"""
    # データ作成
    user = User(email="test@example.com", name="Test User")
    async_db_test.add(user)
    await async_db_test.flush()

    # データ取得
    result = await async_db_test.execute(
        select(User).where(User.email == "test@example.com")
    )
    found = result.scalar_one()
    
    assert found.email == "test@example.com"
    assert found.name == "Test User"
    # テスト終了時に自動ロールバック

@pytest.mark.asyncio
async def test_transaction_isolation(async_db_test):
    """トランザクション分離テスト"""
    # このテストは前のテストのデータを見ない
    result = await async_db_test.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 0  # クリーンな状態からスタート
```

### パフォーマンス比較

| テスト戦略 | 195 テスト実行時間 | 備考 |
|-----------|------------------|------|
| DB 再作成方式 | ~30秒 | 各テストで DB を再作成 |
| Transaction Rollback (同期) | ~3秒 | **9倍高速** |
| Transaction Rollback (非同期) | ~3秒 | 同期と同等の速度 |

---

## 🔍 内部実装の詳細

### URL 変換の仕組み

非同期セッションは同期 DB URL を非同期ドライバー用に自動変換します。

```python
from repom.async_session import convert_to_async_uri

# SQLite
sync_url = "sqlite:///data/db.sqlite3"
async_url = convert_to_async_uri(sync_url)
# => "sqlite+aiosqlite:///data/db.sqlite3"

# PostgreSQL
sync_url = "postgresql://user:pass@localhost/db"
async_url = convert_to_async_uri(sync_url)
# => "postgresql+asyncpg://user:pass@localhost/db"
```

**サポートされるドライバー**:
- SQLite: `aiosqlite`
- PostgreSQL: `asyncpg`
- MySQL: `aiomysql`

---

## 📐 アーキテクチャ

### 同期セッションとの関係

```
repom/
├── session.py          # 同期セッション管理
│   ├── get_session()
│   ├── get_db_session()
│   └── get_db_transaction()
│
└── async_session.py    # 非同期セッション管理 ⭐ NEW
    ├── get_async_session()
    └── get_async_db_session()
```

**設計原則**:
- 同期/非同期の API は独立して動作
- 同じトランザクション管理パターンを採用
- 同じ設定 (`repom.config`) を使用

---

## ⚙️ 設定

### 接続プールの設定

非同期エンジンは `RepomConfig.engine_kwargs` を継承します。

```python
# repom/config.py
class RepomConfig:
    @property
    def engine_kwargs(self) -> dict:
        return {
            'pool_size': 10,       # 常時維持する接続数
            'max_overflow': 20,    # 追加で作成可能な接続数
            'pool_timeout': 30,    # 接続待機のタイムアウト
            'pool_recycle': 3600,  # 接続の再利用期限（秒）
        }
```

### カスタム設定の適用

```python
# your_project/config.py
from repom.config import RepomConfig

class MyConfig(RepomConfig):
    @property
    def engine_kwargs(self) -> dict:
        kwargs = super().engine_kwargs
        kwargs['pool_size'] = 20  # 接続プールを増やす
        return kwargs

def get_repom_config():
    return MyConfig()

# .env
# CONFIG_HOOK=your_project.config:get_repom_config
```

---

## 🐛 トラブルシューティング

### ImportError: cannot import name 'AsyncSession'

**原因**: 非同期ドライバーがインストールされていません。

**解決方法**:
```bash
poetry add aiosqlite  # SQLite の場合
poetry add asyncpg    # PostgreSQL の場合
```

---

### RuntimeError: Event loop is closed

**原因**: pytest-asyncio の設定が不足しています。

**解決方法**:
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

### TypeError: object AsyncSession can't be used in 'await' expression

**原因**: `get_async_session()` の戻り値を直接 await しています。

**間違った例**:
```python
session = await get_async_session()  # ❌ この時点で既に AsyncSession
```

**正しい例**:
```python
session = await get_async_session()  # ✅ get_async_session() 自体が async 関数
await session.execute(...)           # ✅ execute を await
```

---

## 🎯 ベストプラクティス

### 1. FastAPI では依存性注入を使う

```python
# ❌ 非推奨
async def get_user(user_id: int):
    async for session in get_async_db_session():
        result = await session.execute(...)

# ✅ 推奨
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    result = await session.execute(...)
```

### 2. トランザクション管理は自動に任せる

```python
# ❌ 非推奨（手動管理）
session = await get_async_session()
try:
    user = User(email="test@example.com")
    session.add(user)
    await session.commit()
finally:
    await session.close()

# ✅ 推奨（自動管理）
async for session in get_async_db_session():
    user = User(email="test@example.com")
    session.add(user)
    # 自動 commit される
```

### 3. テストでは必ず async fixtures を使う

```python
# ✅ 推奨
@pytest.mark.asyncio
async def test_something(async_db_test):
    # Transaction Rollback パターンで高速化
    user = User(email="test@example.com")
    async_db_test.add(user)
    await async_db_test.flush()
```

---

## 📖 関連ガイド

- **[セッション管理ガイド](session_management_guide.md)**: 同期セッションの詳細
- **[テストガイド](testing_guide.md)**: テスト戦略と Transaction Rollback パターン
- **[BaseRepository & Utilities ガイド](repository_and_utilities_guide.md)**: Repository パターンの使い方

---

## 🔗 参考リンク

- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Users Documentation](https://fastapi-users.github.io/fastapi-users/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
