# repom Database Manager 移行ガイド（fast-domain 向け）

**対象バージョン**: repom 統合後
**作成日**: 2025-12-25
**対象プロジェクト**: fast-domain など repom を使用する外部プロジェクト

---

## 📋 変更サマリー

### 削除されたファイル
- ❌ `repom/db.py`
- ❌ `repom/session.py`
- ❌ `repom/async_session.py`

### 新規ファイル
- ✅ `repom/database.py` - すべてのDB機能を統合

### 主な変更点
1. **インポート元の統一**: すべて `repom.database` から
2. **scoped_session の削除**: `db_session` グローバル変数は廃止
3. **Base.query の削除**: SQLAlchemy 2.0 スタイルへ移行
4. **Lazy initialization**: Engine は初回使用時に作成
5. **関数名の変更**: 一部の関数名が変更

---

## 🔍 影響を受けるインポート一覧

### 削除されたインポート（使用不可）

```python
# ❌ これらはすべてエラーになります
from repom.db import (
    Base,                    # → repom.database.Base
    engine,                  # → get_sync_engine()
    db_session,             # → 削除（scoped_session）
    SessionLocal,           # → 内部実装（直接アクセス不可）
    inspector,              # → get_inspector()
)

from repom.session import (
    get_db_session,         # → repom.database.get_db_session
    get_db_transaction,     # → repom.database.get_db_transaction
    transaction,            # → get_db_transaction に統合
    get_session,            # → 削除
)

from repom.async_session import (
    async_engine,           # → await get_async_engine()
    AsyncSessionLocal,      # → 内部実装（直接アクセス不可）
    get_async_db_session,   # → repom.database.get_async_db_session
    get_async_session,      # → 削除
    convert_to_async_uri,   # → repom.database.convert_to_async_uri
)
```

### 新しいインポート（推奨）

```python
# ✅ 新しいAPI
from repom.database import (
    # Base
    Base,
    
    # 同期API
    get_sync_engine,        # Engine取得
    get_db_session,         # セッション（トランザクションなし）
    get_db_transaction,     # セッション（自動コミット）
    get_inspector,          # Database Inspector
    
    # 非同期API
    get_async_engine,       # 非同期Engine取得
    get_async_db_session,   # 非同期セッション
    get_async_db_transaction,  # 非同期トランザクション
    convert_to_async_uri,   # URL変換ユーティリティ
    
    # Lifecycle（FastAPI用）
    dispose_engines,        # Engine破棄
)
```

---

## 🔧 コードパターン別の移行手順

### 1. FastAPI Depends パターン

#### ❌ Before
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.async_session import get_async_db_session

@app.get("/users")
async def get_users(session: AsyncSession = Depends(get_async_db_session)):
    result = await session.execute(select(User))
    return result.scalars().all()
```

#### ✅ After
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session

# 変更不要！関数名とシグネチャは同じ
@app.get("/users")
async def get_users(session: AsyncSession = Depends(get_async_db_session)):
    result = await session.execute(select(User))
    return result.scalars().all()
```

**変更内容**: インポート元を `repom.database` に変更するだけ

---

### 2. Repository での使用

#### ❌ Before
```python
from repom.session import get_db_session

class UserRepository:
    def get_all(self):
        with get_db_session() as session:
            return session.query(User).all()
```

#### ✅ After
```python
from repom.database import get_db_session

class UserRepository:
    def get_all(self):
        with get_db_session() as session:
            return session.query(User).all()
```

**変更内容**: インポート元を `repom.database` に変更するだけ

---

### 3. トランザクション管理

#### ❌ Before
```python
from repom.session import transaction  # または get_db_transaction

def create_user(name: str):
    with transaction() as session:  # transaction は廃止
        user = User(name=name)
        session.add(user)
        # 自動コミット
```

#### ✅ After
```python
from repom.database import get_db_transaction

def create_user(name: str):
    with get_db_transaction() as session:
        user = User(name=name)
        session.add(user)
        # 自動コミット
```

**変更内容**: 
- `transaction()` → `get_db_transaction()`
- インポート元を `repom.database` に変更

---

### 4. Engine への直接アクセス

#### ❌ Before
```python
from repom.db import engine
from repom.async_session import async_engine

# 同期
Base.metadata.create_all(bind=engine)

# 非同期
async with async_engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

#### ✅ After
```python
from repom.database import get_sync_engine, get_async_engine

# 同期
engine = get_sync_engine()
Base.metadata.create_all(bind=engine)

# 非同期
async_engine = await get_async_engine()
async with async_engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

**変更内容**: 
- モジュールレベル変数ではなく、関数呼び出しで取得
- `async_engine` は `await` が必要

---

### 5. Base.query の削除（SQLAlchemy 1.x → 2.0）

#### ❌ Before（動作しません）
```python
# これはエラーになります
users = User.query.all()
user = User.query.filter_by(email='test@example.com').first()
```

#### ✅ After
```python
from sqlalchemy import select
from repom.database import get_db_session

with get_db_session() as session:
    # query.all() → select + execute + scalars + all
    users = session.execute(select(User)).scalars().all()
    
    # query.filter_by() → select + where + scalar_one_or_none
    stmt = select(User).where(User.email == 'test@example.com')
    user = session.execute(stmt).scalar_one_or_none()
```

**変更内容**: 
- `Model.query` は完全に削除
- `select()` を使った SQLAlchemy 2.0 スタイルに変更

---

### 6. scoped_session (db_session) の使用

#### ❌ Before（動作しません）
```python
from repom.db import db_session

# これらはエラーになります
user = db_session.query(User).first()
db_session.add(user)
db_session.commit()
```

#### ✅ After
```python
from repom.database import get_db_session

with get_db_session() as session:
    user = session.query(User).first()
    session.add(user)
    session.commit()
```

**変更内容**: 
- グローバル `db_session` は廃止
- 明示的に `get_db_session()` でセッション取得
- context manager で管理

---

### 7. Inspector の使用

#### ❌ Before
```python
from repom.db import inspector

tables = inspector.get_table_names()
```

#### ✅ After
```python
from repom.database import get_inspector

inspector = get_inspector()
tables = inspector.get_table_names()
```

**変更内容**: 関数呼び出しで取得

---

## 🔎 プロジェクト内の検索コマンド

### 1. 影響を受けるインポートを検索

```bash
# すべての旧インポートを検索
grep -r "from repom.db import" --include="*.py"
grep -r "from repom.session import" --include="*.py"
grep -r "from repom.async_session import" --include="*.py"

# Windows PowerShell
Select-String -Path "**/*.py" -Pattern "from repom\.(db|session|async_session) import"
```

### 2. Base.query の使用箇所を検索

```bash
# Model.query のパターンを検索
grep -r "\.query\." --include="*.py"

# Windows PowerShell
Select-String -Path "**/*.py" -Pattern "\.query\."
```

### 3. scoped_session (db_session) の使用を検索

```bash
grep -r "db_session\." --include="*.py"

# Windows PowerShell
Select-String -Path "**/*.py" -Pattern "db_session\."
```

---

## ✅ 移行チェックリスト

fast-domain プロジェクトで以下を確認してください：

### インポート変更
- [ ] すべての `from repom.db import` を検索・置換
- [ ] すべての `from repom.session import` を検索・置換
- [ ] すべての `from repom.async_session import` を検索・置換
- [ ] `Base` のインポート元を `repom.database` に変更

### API変更
- [ ] `transaction()` を `get_db_transaction()` に変更
- [ ] `engine` を `get_sync_engine()` に変更
- [ ] `async_engine` を `await get_async_engine()` に変更
- [ ] `inspector` を `get_inspector()` に変更

### 非推奨機能の削除
- [ ] `Base.query` の使用を `select()` に変更
- [ ] `db_session` (scoped_session) の使用を削除
- [ ] `Model.query.all()` などを `session.execute(select(Model))` に変更

### テスト
- [ ] 全テストを実行して動作確認
- [ ] FastAPI エンドポイントの動作確認
- [ ] Repository パターンの動作確認
- [ ] CLI スクリプトの動作確認

---

## 📊 変更の影響範囲マトリックス

| 使用パターン | 影響度 | 必要な作業 |
|------------|--------|----------|
| FastAPI Depends | 🟢 低 | インポート変更のみ |
| Repository内セッション | 🟢 低 | インポート変更のみ |
| トランザクション管理 | 🟡 中 | 関数名変更 + インポート |
| Engine直接アクセス | 🟡 中 | 関数呼び出しに変更 |
| Base.query 使用 | 🔴 高 | SQLAlchemy 2.0 に書き換え |
| scoped_session 使用 | 🔴 高 | context manager に書き換え |

---

## 🚨 よくあるエラーと対処法

### エラー1: ModuleNotFoundError

```python
ModuleNotFoundError: No module named 'repom.db'
```

**原因**: 旧モジュールが削除されている

**対処法**: インポートを `repom.database` に変更

---

### エラー2: AttributeError: 'User' object has no attribute 'query'

```python
AttributeError: type object 'User' has no attribute 'query'
```

**原因**: `Base.query` が削除された

**対処法**: `select()` を使った SQLAlchemy 2.0 スタイルに変更

---

### エラー3: NameError: name 'db_session' is not defined

```python
NameError: name 'db_session' is not defined
```

**原因**: scoped_session が削除された

**対処法**: `get_db_session()` または `get_db_transaction()` を使用

---

### エラー4: NameError: name 'transaction' is not defined

```python
NameError: name 'transaction' is not defined
```

**原因**: `transaction()` 関数が削除された

**対処法**: `get_db_transaction()` に変更

---

## 📝 移行作業の推奨順序

1. **検索・確認フェーズ**
   - grep で影響箇所をすべてリストアップ
   - 変更が必要なファイル数を把握

2. **簡単な変更から開始**
   - インポート変更のみで済む箇所から着手
   - FastAPI Depends パターンは変更が少ない

3. **中程度の変更**
   - `transaction()` → `get_db_transaction()`
   - Engine アクセスの変更

4. **難易度の高い変更**
   - `Base.query` の書き換え
   - scoped_session の置き換え

5. **テスト・検証**
   - 変更したファイルごとにテスト実行
   - 統合テストで全体動作確認

---

## 🔗 関連ドキュメント

- [Issue #015: Database Manager Unification](../issue/active/015_database_manager_unification.md)
- [Session Management Guide](./session_management_guide.md)
- [Async Session Guide](./async_session_guide.md)
- [Testing Guide](./testing_guide.md)

---

## 💡 Tips

### 一括置換の例（VS Code）

1. **インポート置換**
   - 検索: `from repom\.db import`
   - 置換: `from repom.database import`

2. **transaction 関数名**
   - 検索: `with transaction\(\) as`
   - 置換: `with get_db_transaction() as`

### Git での変更追跡

```bash
# 変更が必要なファイルをステージング前に確認
git diff --name-only | grep ".py$"

# コミットメッセージ例
git commit -m "refactor: migrate to repom.database API"
```

---

**最終更新**: 2025-12-25
