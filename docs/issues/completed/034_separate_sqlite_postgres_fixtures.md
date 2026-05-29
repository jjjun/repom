# Issue #035: SQLite/PostgreSQL Fixture の分離

**ステータス**: 🔴 未着手

**作成日**: 2026-02-04

**優先度**: 中

**複雑度**: 中

**親Issue**: [Issue #028: テストアーキテクチャの複雑性](028_test_architecture_complexity.md)

**前提Issue**: Issue #034 (autouse=True削除) - 先に実装推奨

---

## 問題の説明

現在、`setup_repom_db_tables` フィクスチャは**SQLiteとPostgreSQLの両方を単一のfixtureで扱おうとしている**ため、条件分岐が複雑化している。

### 現状のコード

```python
# tests/conftest.py (line 75-85)
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    # ... SQLite用のsetup ...
    
    # PostgreSQL特有の条件分岐
    from repom.config import config
    exec_env = os.getenv('EXEC_ENV', 'test')
    
    if not (config.db_type == 'postgres' and exec_env == 'test'):
        # 非同期engine作成（PostgreSQL + test環境の場合はスキップ）
        async def create_async_tables():
            async_engine = await get_async_engine()
            # ...
```

### 問題点

#### 1. **複雑な条件式**

```python
if not (config.db_type == 'postgres' and exec_env == 'test'):
    # 非同期エンジン作成
```

**意味**:
- `db_type='postgres'` **かつ** `exec_env='test'` の場合は**スキップ**
- それ以外は**実行**

**問題**:
- 条件が複雑で理解が困難
- なぜこの条件が必要か不明瞭
- メンテナンスが困難

#### 2. **2つのconftest.pyでfixtureが衝突**

```python
# tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    # SQLite前提の実装
    # + PostgreSQL条件分岐

# tests/integration_tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_postgres_tables():
    # PostgreSQL前提の実装
    if config.db_type != 'postgres':
        return  # 早期リターン
```

**問題**:
- 両方autouse=Trueで実行される
- どちらが実際に動作しているか不明瞭
- 子のfixtureが実質的に意味をなさない

#### 3. **要件の違いを無理に統一**

SQLiteとPostgreSQLで必要なsetupが異なる：

| 要件 | SQLite | PostgreSQL |
|------|--------|-----------|
| 同期engine | ✅ 必要 | ✅ 必要 |
| 非同期engine | ✅ 必要 | ❌ 不要（パスワード問題） |
| テーブル作成 | ✅ 自動 | ✅ 自動 |
| クリーンアップ | ✅ :memory:なので不要 | ⚠️ 必要（オプション） |

**問題**:
- 異なる要件を1つのfixtureで扱おうとしている
- 条件分岐が増える
- 可読性が低下

---

## 期待される動作

**SQLiteとPostgreSQLで別々のfixtureを用意する**。

### 理想的な構造

```python
# tests/conftest.py
@pytest.fixture(scope='session')
def setup_sqlite_tables():
    """SQLite専用のsetup"""
    # 同期engine作成
    # 非同期engine作成
    # テーブル作成
    pass

@pytest.fixture(scope='session')
def setup_postgres_tables():
    """PostgreSQL専用のsetup"""
    # 同期engine作成のみ
    # 非同期engineは作成しない（パスワード問題）
    # テーブル作成
    pass

# 共通のエイリアス（後方互換性）
@pytest.fixture(scope='session')
def setup_db_tables(config):
    """db_typeに応じて適切なfixtureを選択"""
    if config.db_type == 'postgres':
        return setup_postgres_tables()
    else:
        return setup_sqlite_tables()
```

---

## 提案される解決策

### アプローチ1: Fixture分離（推奨）

```python
# tests/conftest.py

@pytest.fixture(scope='session')
def setup_sqlite_tables():
    """SQLite専用のテーブルsetup"""
    from repom.models.base_model import Base
    from repom.database import get_sync_engine, get_async_engine
    from repom.utility import load_models
    import asyncio

    load_models()
    
    # 同期engine
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    
    # 非同期engine（SQLiteは必要）
    async def create_async_tables():
        async_engine = await get_async_engine()
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    asyncio.run(create_async_tables())
    
    yield
    
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope='session')
def setup_postgres_tables():
    """PostgreSQL専用のテーブルsetup"""
    from repom.models.base_model import Base
    from repom.database import get_sync_engine
    from repom.utility import load_models

    load_models()
    
    # 同期engineのみ（PostgreSQLは非同期不要）
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # PostgreSQLはクリーンアップしない（データ永続化）
    # Base.metadata.drop_all(bind=engine)


# 後方互換性のためのエイリアス
@pytest.fixture(scope='session')
def setup_db_tables(request):
    """
    db_typeに応じて適切なfixtureを選択
    
    後方互換性のため。新しいテストは直接
    setup_sqlite_tables または setup_postgres_tables を使用すること。
    """
    from repom.config import config
    
    if config.db_type == 'postgres':
        # PostgreSQL用fixtureを実行
        yield from setup_postgres_tables(request)
    else:
        # SQLite用fixtureを実行
        yield from setup_sqlite_tables(request)
```

### アプローチ2: parametrize（将来的）

```python
# pytest.ini または pyproject.toml
[tool.pytest.ini_options]
markers = [
    "sqlite: SQLite database tests",
    "postgres: PostgreSQL database tests"
]

# テストファイル
@pytest.mark.sqlite
def test_sqlite_feature(setup_sqlite_tables, db_test):
    pass

@pytest.mark.postgres
def test_postgres_feature(setup_postgres_tables, db_test):
    pass
```

---

## 影響範囲

### 変更が必要なファイル

1. **tests/conftest.py**
   - `setup_repom_db_tables` を分離
   - `setup_sqlite_tables` 作成
   - `setup_postgres_tables` 作成
   - 後方互換性のため `setup_db_tables` エイリアス作成

2. **tests/integration_tests/conftest.py**
   - 既存の `setup_postgres_tables` を削除または統合

3. **テストファイル（オプション）**
   - 明示的に `setup_sqlite_tables` または `setup_postgres_tables` を使用
   - `setup_db_tables` のままでも動作（後方互換性）

### 影響を受けるテスト

- Unit tests: SQLite専用
- Integration tests: PostgreSQL専用
- Behavior tests: SQLite専用

**リスク評価**: 中
- fixture構造を変更するため、慎重なテストが必要
- 後方互換性を保つため、既存テストへの影響は最小限

---

## 実装計画

### Phase 1: Fixture分離（45分）

1. **tests/conftest.py にSQLite専用fixtureを作成**
   ```python
   @pytest.fixture(scope='session')
   def setup_sqlite_tables():
       # 既存の setup_repom_db_tables から条件分岐を削除
       # SQLite用のコードのみ抽出
   ```

2. **tests/conftest.py にPostgreSQL専用fixtureを作成**
   ```python
   @pytest.fixture(scope='session')
   def setup_postgres_tables():
       # 非同期engine作成を削除
       # PostgreSQL用のコードのみ
   ```

3. **後方互換性のためのエイリアス作成**
   ```python
   @pytest.fixture(scope='session')
   def setup_db_tables(request):
       # db_typeに応じて適切なfixtureを選択
   ```

### Phase 2: integration_tests/conftest.py 整理（15分）

4. **重複fixtureを削除または統合**
   ```python
   # tests/integration_tests/conftest.py
   # 既存の setup_postgres_tables を削除
   # 親の fixture を使用
   ```

### Phase 3: テストと検証（30分）

5. **Unit テストを実行（SQLite）**
   ```bash
   poetry run pytest tests/unit_tests/ -v
   ```

6. **Integration テストを実行（PostgreSQL）**
   ```bash
   poetry run pytest tests/integration_tests/ -v
   ```

7. **Behavior テストを実行（SQLite）**
   ```bash
   poetry run pytest tests/behavior_tests/ -v
   ```

**総見積もり**: 90分

---

## テスト計画

### 1. SQLite Unit Tests

```bash
# EXEC_ENV='test' (デフォルト)
poetry run pytest tests/unit_tests/ -v
```

**期待結果**:
- `setup_sqlite_tables` が使用される
- 非同期engineが作成される
- 全テストがパス

### 2. PostgreSQL Integration Tests

```bash
# EXEC_ENV='test' + DB_TYPE='postgres'
poetry run pytest tests/integration_tests/ -v
```

**期待結果**:
- `setup_postgres_tables` が使用される
- 非同期engineは作成されない
- 全テストがパス

### 3. 後方互換性テスト

```bash
# setup_db_tables を使用する既存テスト
poetry run pytest tests/ -v
```

**期待結果**:
- エイリアス経由で適切なfixtureが呼ばれる
- 全テストがパス

---

## 完了基準

- ✅ `setup_sqlite_tables` fixtureが作成されている
- ✅ `setup_postgres_tables` fixtureが作成されている
- ✅ 後方互換性のための `setup_db_tables` エイリアスが作成されている
- ✅ 複雑な条件分岐（`if not (config.db_type == 'postgres' and exec_env == 'test')`）が削除されている
- ✅ tests/integration_tests/conftest.py の重複fixtureが整理されている
- ✅ 全テスト（Unit/Behavior/Integration）がパスする
- ✅ SQLiteテストで非同期engineが作成される
- ✅ PostgreSQLテストで非同期engineが作成されない

---

## メリット

### 1. **可読性向上**
- 条件分岐が削減される
- SQLiteとPostgreSQLの違いが明確

### 2. **メンテナンス性向上**
- 各DB用の要件が分離されている
- 変更時の影響範囲が明確

### 3. **拡張性向上**
- 新しいDB（MySQL等）を追加しやすい
- DB固有の処理を追加しやすい

### 4. **デバッグが容易**
- どのfixtureが実行されているか明確
- DB固有の問題を切り分けやすい

---

## 関連Issue

- **親Issue**: [Issue #028: テストアーキテクチャの複雑性](028_test_architecture_complexity.md)
- **前提**: Issue #034 (autouse=True削除) - 先に実装推奨
- **関連**: Issue #036 (fixture scope見直し) - 独立して実装可能

---

## 備考

### Issue #034との関係

Issue #034（autouse削除）を先に実装することを推奨：

1. **理由**: autouse=Trueのままだと、両方のfixtureが自動実行される可能性
2. **順序**: 
   - ステップ1: Issue #034で autouse削除
   - ステップ2: Issue #035で fixture分離
   - ステップ3: テストファイルで適切なfixtureを明示的に指定

### 将来的な改善（別Issue）

- pytest markers (`@pytest.mark.sqlite`) の導入
- conftest.py の階層的な整理
- DB type別のディレクトリ分割

---

**最終更新**: 2026-02-04
