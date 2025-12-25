# Issue #015: Database Manager Unification - セッション・エンジン管理の統合

**ステータス**: 🔴 未着手

**作成日**: 2025-12-25

**優先度**: 高

**種別**: リファクタリング（破壊的変更）

**影響範囲**: 広範囲（コア機能の変更）

---

## 📋 目次

1. [問題の背景](#問題の背景)
2. [現状の問題点](#現状の問題点)
3. [提案する解決策](#提案する解決策)
4. [実装計画](#実装計画)
5. [移行ガイド](#移行ガイド)
6. [テスト戦略](#テスト戦略)
7. [影響を受けるファイル](#影響を受けるファイル)

---

## 問題の背景

現在、repom のデータベースセッション・エンジン管理は3つのファイルに分散しています：

```
repom/
├── db.py              # 同期 Engine, Base, scoped_session
├── session.py         # 同期 Session 管理関数
└── async_session.py   # 非同期 Engine, Session 管理
```

### 現状の問題点

#### 1. **モジュールレベルでの即座な Engine 作成**

```python
# ❌ 問題: import 時に Engine が作成される
# repom/db.py
engine = create_engine(config.db_url, **config.engine_kwargs)

# repom/async_session.py
async_engine = create_async_engine(async_db_url, ...)
```

**問題：**
- Lazy initialization ではない（import するだけで接続が作られる）
- テストでモックが困難
- FastAPI の lifespan で dispose できない
- 設定変更が困難

#### 2. **scoped_session の使用（SQLAlchemy 1.x スタイル）**

```python
# ❌ 古いパターン
db_session = scoped_session(...)
Base.query = db_session.query_property()

# 使用例（非推奨パターン）
users = User.query.all()
```

**問題：**
- SQLAlchemy 2.0 では非推奨
- スレッドローカル依存（async では使えない）
- 明示的なセッション管理が推奨される

#### 3. **管理の分散**

- Engine 管理: `db.py`, `async_session.py`
- Session 管理: `session.py`, `async_session.py`
- Base: `db.py`
- Inspector: `db.py`

**問題：**
- 責任が分散
- 一貫性のない API
- lifespan 管理が困難

---

## 提案する解決策

### 新しいアーキテクチャ：DatabaseManager

すべてのデータベース関連機能を `database.py` に統合し、DatabaseManager クラスで一元管理します。

```python
# repom/database.py (新規作成)
class DatabaseManager:
    """
    Sync/Async Engine と Session の統合管理
    
    Features:
    - Lazy initialization（必要になるまで作成しない）
    - Lifespan management（FastAPI 統合）
    - 同期・非同期の両方をサポート
    - Session factory 提供
    """
    
    def __init__(self):
        self._sync_engine: Optional[Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._lock = asyncio.Lock()
    
    # Sync API
    def get_sync_engine(self) -> Engine:
        """Sync Engine を取得（lazy init）"""
    
    def get_sync_session_factory(self) -> sessionmaker:
        """Sync Session Factory を取得"""
    
    @contextmanager
    def get_sync_session(self) -> Generator[Session, None, None]:
        """Sync Session を取得（context manager）"""
    
    @contextmanager
    def get_sync_transaction(self) -> Generator[Session, None, None]:
        """トランザクション管理付き Sync Session"""
    
    def get_inspector(self):
        """Database inspector を取得（schema introspection）"""
    
    # Async API
    async def get_async_engine(self) -> AsyncEngine:
        """Async Engine を取得（lazy init）"""
    
    async def get_async_session_factory(self) -> async_sessionmaker:
        """Async Session Factory を取得"""
    
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Async Session を取得（async context manager）"""
    
    async def get_async_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """トランザクション管理付き Async Session"""
    
    # Lifecycle
    def dispose_sync(self):
        """Sync Engine を破棄"""
    
    async def dispose_async(self):
        """Async Engine を破棄"""
    
    async def dispose_all(self):
        """すべての Engine を破棄"""
    
    @asynccontextmanager
    async def lifespan_context(self):
        """FastAPI lifespan として使用"""
        yield
        await self.dispose_all()
```

### 公開 API（後方互換性を考慮）

```python
# グローバルインスタンス
_db_manager = DatabaseManager()

# Sync API
def get_sync_engine() -> Engine: ...
def get_db_session() -> Generator[Session, None, None]: ...
def get_db_transaction() -> Generator[Session, None, None]: ...
def get_inspector(): ...

# Async API
async def get_async_engine() -> AsyncEngine: ...
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]: ...
async def get_async_db_transaction() -> AsyncGenerator[AsyncSession, None]: ...

# Lifecycle
async def dispose_engines(): ...
def get_lifespan_manager(): ...

# Base (別ファイルへ移動を検討)
Base = declarative_base()
```

---

## 実装計画

### Phase 1: 新規ファイル作成 ✅

- [ ] `repom/database.py` を作成
  - [ ] `DatabaseManager` クラス実装
  - [ ] 公開 API 関数実装
  - [ ] URL 変換ユーティリティ
  - [ ] docstring 追加

### Phase 2: 既存コードの移行 🔄

#### 2.1 Base の扱い

- [ ] `Base` を `repom/database.py` に移動
- [ ] `Base.query` を削除（SQLAlchemy 2.0 スタイルへ）
- [ ] すべてのインポートを更新：
  ```python
  # Before
  from repom.db import Base
  
  # After
  from repom.database import Base
  ```

#### 2.2 Session 関数の移行

- [ ] `repom/session.py` の機能を `database.py` に統合
- [ ] `repom/async_session.py` の機能を `database.py` に統合
- [ ] 関数名は維持（後方互換性）

#### 2.3 内部コードの更新

- [ ] `repom/base_model.py`: `from repom.db import Base` → `from repom.database import Base`
- [ ] `repom/base_repository.py`: `from repom.db import db_session` → 削除（使用していない）
- [ ] `repom/testing.py`: `from repom.db import Base` → `from repom.database import Base`
- [ ] `repom/scripts/db_*.py`: Engine 取得方法を更新

#### 2.4 scoped_session の削除

- [ ] `db_session = scoped_session(...)` を完全削除
- [ ] `Base.query` を削除
- [ ] 影響を受けるコードを検索・更新

### Phase 3: テストの更新 🧪

- [ ] `tests/conftest.py`: Fixture を新しい API に対応
- [ ] `tests/unit_tests/test_session.py`: 新しい API のテスト
- [ ] `tests/unit_tests/test_async_session.py`: 新しい API のテスト
- [ ] すべてのテストで `from repom.database import` に更新
- [ ] 全テスト実行・パス確認

### Phase 4: ドキュメント更新 📚

- [ ] `docs/guides/session_management_guide.md`: 新しい API の使い方
- [ ] `docs/guides/async_session_guide.md`: 新しい API の使い方
- [ ] `docs/guides/async_repository_guide.md`: インポート例の更新
- [ ] `docs/guides/repository_and_utilities_guide.md`: インポート例の更新
- [ ] `README.md`: クイックスタートの更新
- [ ] `AGENTS.md`: 技術スタックの更新

### Phase 5: 旧ファイルの削除 🗑️

- [ ] `repom/db.py` を削除
- [ ] `repom/session.py` を削除
- [ ] `repom/async_session.py` を削除
- [ ] `__all__` の更新

### Phase 6: 最終確認 ✅

- [ ] 全テスト実行（195+ tests）
- [ ] Linter チェック
- [ ] 型チェック（mypy）
- [ ] ドキュメントのビルド確認

---

## 移行ガイド

### 外部プロジェクト（fast-domain など）向け移行手順

#### Step 1: インポートの更新

```python
# ========================================
# Before (旧 API)
# ========================================

# Sync Session
from repom.session import get_db_session, get_db_transaction, transaction
from repom.db import SessionLocal, Base, engine, inspector

# Async Session
from repom.async_session import get_async_db_session, AsyncSessionLocal, async_engine

# ========================================
# After (新 API)
# ========================================

# Sync Session
from repom.database import get_db_session, get_db_transaction
from repom.database import Base, get_sync_engine, get_inspector

# Async Session
from repom.database import get_async_db_session
from repom.database import get_async_engine

# Note: SessionLocal, AsyncSessionLocal は内部実装なので直接アクセス不可
# 必要な場合は get_sync_engine() / get_async_engine() を使用
```

#### Step 2: Base.query の削除

```python
# ========================================
# Before (SQLAlchemy 1.x スタイル)
# ========================================

# ❌ 非推奨
users = User.query.all()
user = User.query.filter_by(email='test@example.com').first()

# ========================================
# After (SQLAlchemy 2.0 スタイル)
# ========================================

# ✅ 推奨
from sqlalchemy import select

with get_db_session() as session:
    users = session.execute(select(User)).scalars().all()
    user = session.execute(
        select(User).where(User.email == 'test@example.com')
    ).scalar_one_or_none()
```

#### Step 3: FastAPI での使用

```python
# ========================================
# Before
# ========================================

from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.async_session import get_async_db_session

app = FastAPI()

@app.get("/users")
async def get_users(session: AsyncSession = Depends(get_async_db_session)):
    result = await session.execute(select(User))
    return result.scalars().all()

# ========================================
# After
# ========================================

from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session, get_lifespan_manager

# Lifespan management の追加（推奨）
app = FastAPI(lifespan=get_lifespan_manager())

@app.get("/users")
async def get_users(session: AsyncSession = Depends(get_async_db_session)):
    result = await session.execute(select(User))
    return result.scalars().all()
```

#### Step 4: CLI スクリプトでの使用

```python
# ========================================
# Before
# ========================================

from repom.session import transaction

def main():
    with transaction() as session:
        user = User(name="test")
        session.add(user)
        # 自動コミット

# ========================================
# After
# ========================================

from repom.database import get_db_transaction

def main():
    with get_db_transaction() as session:
        user = User(name="test")
        session.add(user)
        # 自動コミット
```

#### Step 5: Engine への直接アクセス

```python
# ========================================
# Before
# ========================================

from repom.db import engine
from repom.async_session import async_engine

# テーブル作成など
Base.metadata.create_all(bind=engine)

# ========================================
# After
# ========================================

from repom.database import get_sync_engine, get_async_engine

# 同期
engine = get_sync_engine()
Base.metadata.create_all(bind=engine)

# 非同期
async_engine = await get_async_engine()
async with async_engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

### 移行チェックリスト

外部プロジェクトで以下を確認してください：

- [ ] すべての `from repom.db import` を `from repom.database import` に変更
- [ ] すべての `from repom.session import` を `from repom.database import` に変更
- [ ] すべての `from repom.async_session import` を `from repom.database import` に変更
- [ ] `Base.query` の使用を `select()` に変更
- [ ] `db_session` (scoped_session) の使用を削除
- [ ] FastAPI に `lifespan` を追加（推奨）
- [ ] すべてのテストが通過することを確認

---

## テスト戦略

### 新規テスト

#### `tests/unit_tests/test_database_manager.py`

```python
"""
DatabaseManager の単体テスト
"""

class TestDatabaseManager:
    def test_lazy_initialization_sync(self):
        """Sync Engine は lazy initialization される"""
        manager = DatabaseManager()
        assert manager._sync_engine is None
        engine = manager.get_sync_engine()
        assert manager._sync_engine is not None
        assert isinstance(engine, Engine)
    
    async def test_lazy_initialization_async(self):
        """Async Engine は lazy initialization される"""
        manager = DatabaseManager()
        assert manager._async_engine is None
        engine = await manager.get_async_engine()
        assert manager._async_engine is not None
        assert isinstance(engine, AsyncEngine)
    
    def test_sync_session_context_manager(self):
        """Sync Session の context manager 動作確認"""
        manager = DatabaseManager()
        with manager.get_sync_session() as session:
            assert isinstance(session, Session)
        # セッションが閉じられていることを確認
    
    async def test_async_session_context_manager(self):
        """Async Session の context manager 動作確認"""
        manager = DatabaseManager()
        async with manager.get_async_session() as session:
            assert isinstance(session, AsyncSession)
    
    def test_dispose_sync(self):
        """Sync Engine の dispose 動作確認"""
        manager = DatabaseManager()
        engine = manager.get_sync_engine()
        manager.dispose_sync()
        assert manager._sync_engine is None
    
    async def test_dispose_async(self):
        """Async Engine の dispose 動作確認"""
        manager = DatabaseManager()
        await manager.get_async_engine()
        await manager.dispose_async()
        assert manager._async_engine is None
```

### 既存テストの更新

- [ ] `tests/conftest.py`: Fixture を更新
- [ ] `tests/unit_tests/test_session.py`: インポート更新
- [ ] `tests/unit_tests/test_async_session.py`: インポート更新
- [ ] すべてのテストファイルでインポート更新

### テスト実行

```bash
# 全テスト実行
poetry run pytest tests/

# 特定のテストのみ
poetry run pytest tests/unit_tests/test_database_manager.py -v
```

---

## 影響を受けるファイル

### repom 内部

#### 削除されるファイル
- `repom/db.py` ❌
- `repom/session.py` ❌
- `repom/async_session.py` ❌

#### 新規作成されるファイル
- `repom/database.py` ✅

#### 更新が必要なファイル
- `repom/base_model.py`
- `repom/base_repository.py`
- `repom/testing.py`
- `repom/scripts/db_create.py`
- `repom/scripts/db_delete.py`
- `repom/scripts/db_backup.py`
- `repom/scripts/db_sync_master.py`

### テストファイル

#### 更新が必要なテスト
- `tests/conftest.py` ⚠️ 重要
- `tests/db_test_fixtures.py` ⚠️ 重要
- `tests/unit_tests/test_session.py`
- `tests/unit_tests/test_async_session.py`
- `tests/behavior_tests/test_date_type_comparison.py`
- `tests/behavior_tests/test_migration_no_id.py`
- `tests/behavior_tests/test_unique_key_handling.py`
- その他、`from repom.db import` を使用しているすべてのテスト

### ドキュメント

#### 更新が必要なドキュメント
- `README.md`
- `AGENTS.md`
- `docs/guides/session_management_guide.md`
- `docs/guides/async_session_guide.md`
- `docs/guides/async_repository_guide.md`
- `docs/guides/repository_and_utilities_guide.md`
- `docs/guides/testing_guide.md`

---

## リスクと対策

### リスク1: 破壊的変更

**対策:**
- 移行ガイドを充実させる
- 具体的なコード例を提供
- fast-domain での実践的な移行を通じてガイドを改善

### リスク2: テストの更新漏れ

**対策:**
- grep で全インポートを検索
- テストを段階的に更新
- 全テスト実行で確認

### リスク3: パフォーマンス懸念

**対策:**
- Lazy initialization により、実際にはパフォーマンス向上
- 接続プールの設定は従来通り
- ベンチマークテストで確認

---

## メリット

### 1. Lazy Initialization
- import 時に Engine を作成しない
- 必要になるまでリソースを消費しない
- テスト時のモックが容易

### 2. Lifespan Management
- FastAPI の lifespan で適切に Engine を破棄
- リソースリークを防ぐ
- Graceful shutdown

### 3. 一貫性のある API
- すべての機能が `repom.database` に統合
- 同期・非同期で統一されたインターフェース
- ドキュメントが整理される

### 4. SQLAlchemy 2.0 対応
- `Base.query` の削除
- 現代的なクエリスタイル
- 型安全性の向上

### 5. テスタビリティ
- DatabaseManager のモックが容易
- 各機能の単体テストが書きやすい
- テスト用の Engine 切り替えが簡単

---

## 完了条件

- [ ] `repom/database.py` 実装完了
- [ ] すべてのインポートを更新
- [ ] `Base.query` 削除
- [ ] `scoped_session` 削除
- [ ] 旧ファイル（db.py, session.py, async_session.py）削除
- [ ] 全テスト（195+ tests）パス
- [ ] ドキュメント更新完了
- [ ] 移行ガイド作成完了
- [ ] fast-domain での移行成功

---

## 関連 Issue

- Issue #005: 柔軟な auto_import_models 設定（Base の扱いに関連）
- Issue #011: セッション管理ユーティリティの追加（この issue で統合される）

---

## 参考資料

- [SQLAlchemy 2.0 Documentation - Using ORM Declarative Forms](https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html)
- [SQLAlchemy 2.0 Documentation - Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [FastAPI - Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

---

**最終更新**: 2025-12-25
**作成者**: AI Assistant
**レビュー待ち**: repom メンテナー
