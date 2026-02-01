　# Issue #028: テストアーキテクチャの複雑性

## 問題の概要

現在のテスト構造は、デフォルトでSQLiteを使用し、PostgreSQLテスト時に動作を変更する必要があるため、複雑になっている。

## 現在の問題点

### 1. **conftest.py の複雑な条件分岐**

```python
# tests/conftest.py (line 6)
os.environ['EXEC_ENV'] = 'test'  # ハードコード

# setup_repom_db_tables fixture (lines 33-90)
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    # 問題1: no_db_setup マーカーのチェック（使われていない）
    if request.node.get_closest_marker('no_db_setup'):
        yield
        return
    
    # 問題2: PostgreSQL特有の条件分岐
    if not (db_type == 'postgres' and exec_env == 'dev'):
        # async engine 作成
```

**問題**:
- `autouse=True` で全テストに強制適用
- PostgreSQL と SQLite の混在で条件が複雑化
- session scope なのに個別テストで制御不可

### 2. **環境変数の上書き合戦**

```python
# tests/conftest.py (line 6)
os.environ['EXEC_ENV'] = 'test'

# tests/integration_tests/conftest.py (line 8)
os.environ['EXEC_ENV'] = 'dev'  # 上書き

# tests/integration_tests/test_postgres_integration.py (line 7)
os.environ['EXEC_ENV'] = 'dev'  # 念のため再上書き

# tests/unit_tests/test_config_postgres.py (line 13)
if 'DB_TYPE' in os.environ:
    del os.environ['DB_TYPE']  # クリア
```

**問題**:
- 環境変数の上書きが複数箇所で発生
- どの設定が最終的に適用されるか不明瞭
- テスト実行順序に依存する可能性

### 3. **矛盾したテスト設計**

```python
# tests/unit_tests/test_config_postgres.py
# PostgreSQL config のテストなのに SQLite 環境で実行
if 'DB_TYPE' in os.environ:
    del os.environ['DB_TYPE']  # PostgreSQL設定をテストしたいのに削除
```

**問題**:
- PostgreSQL プロパティをテストするのに SQLite 環境
- 実際の使用シナリオと乖離

### 4. **fixture の重複と衝突**

```python
# tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    # SQLite 前提の実装

# tests/integration_tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_postgres_tables():
    # PostgreSQL 前提の実装（実際には使われていない）
```

**問題**:
- 両方 autouse=True なので両方実行される
- PostgreSQL 統合テスト時に親の fixture が先に実行される
- 子の fixture が実質的に意味をなさない

## 根本原因

1. **単一の conftest.py で全てを制御しようとしている**
   - SQLite と PostgreSQL で異なる要件があるのに同じ fixture
   
2. **EXEC_ENV のハードコード**
   - `os.environ['EXEC_ENV'] = 'test'` が最初に固定される
   
3. **autouse=True の濫用**
   - 全テストで不要な setup が実行される
   
4. **DB接続を必要としないテストでも DB setup が実行される**
   - config プロパティのみのテストでも engine 作成

## 影響範囲

### 正常動作しているもの
- ✅ SQLite 単体テスト (db_test fixture 使用)
- ✅ PostgreSQL 統合テスト (回避策で動作)
- ✅ PostgreSQL config 単体テスト (環境変数削除で動作)

### 問題が顕在化しているもの
- ⚠️ テスト実行時の複雑な条件分岐
- ⚠️ 環境変数の管理が煩雑
- ⚠️ 新しいテストを追加する際の学習コスト

## 改善案

### 案1: fixture を autouse=False にする

```python
# tests/conftest.py
@pytest.fixture(scope='session')  # autouse 削除
def setup_db_tables():
    # 必要なテストでのみ明示的に使用
    pass

# 使用例
def test_something(setup_db_tables, db_test):
    pass
```

**メリット**:
- 不要な setup 実行を削減
- テストごとに制御可能

**デメリット**:
- 全テストに fixture を追加する必要

### 案2: DB type 別に conftest.py を分離

```
tests/
├── conftest.py                    # 共通設定のみ
├── unit_tests/
│   ├── conftest.py               # SQLite 専用
│   └── test_*.py
├── integration_tests/
│   ├── sqlite/
│   │   ├── conftest.py          # SQLite 統合テスト用
│   │   └── test_*.py
│   └── postgres/
│       ├── conftest.py          # PostgreSQL 統合テスト用
│       └── test_*.py
```

**メリット**:
- 明確な責任分離
- 環境変数の衝突なし

**デメリット**:
- ディレクトリ構造の大幅変更

### 案3: pytest の ini オプションで DB type を制御

```ini
# pytest.ini または pyproject.toml
[tool.pytest.ini_options]
markers = [
    "sqlite: SQLite database tests",
    "postgres: PostgreSQL database tests",
    "no_db: No database connection required"
]
```

```python
# 実行方法
pytest -m sqlite          # SQLite テストのみ
pytest -m postgres        # PostgreSQL テストのみ
pytest -m "not postgres"  # PostgreSQL 以外
```

**メリット**:
- pytest 標準機能
- 条件分岐を marker で整理

**デメリット**:
- 全テストに marker 追加必要

### 案4: 環境変数を pytest 起動時に設定

```python
# tests/conftest.py
import os
import pytest

def pytest_configure(config):
    # コマンドライン引数から DB type を取得
    db_type = config.getoption("--db-type", default="sqlite")
    os.environ['DB_TYPE'] = db_type
    
    # EXEC_ENV もオプション化
    exec_env = config.getoption("--exec-env", default="test")
    os.environ['EXEC_ENV'] = exec_env

def pytest_addoption(parser):
    parser.addoption(
        "--db-type",
        action="store",
        default="sqlite",
        help="Database type: sqlite or postgres"
    )
    parser.addoption(
        "--exec-env",
        action="store",
        default="test",
        help="Execution environment: dev, test, or prod"
    )
```

```bash
# 使用例
pytest --db-type=postgres --exec-env=dev tests/integration_tests/
pytest --db-type=sqlite tests/unit_tests/
```

**メリット**:
- 環境変数のハードコード削除
- 明示的な制御
- ファイル内での環境変数上書き不要

**デメリット**:
- 既存のテスト実行方法が変わる

## 推奨案

**案4 (pytest オプション) + 案1 (autouse=False) の組み合わせ**

理由:
1. 環境変数のハードコードを排除
2. fixture を必要なテストでのみ使用
3. 既存のディレクトリ構造を維持
4. pytest 標準機能で実装

実装ステップ:
1. pytest_configure で環境変数を設定
2. setup_repom_db_tables を autouse=False に変更
3. 必要なテストファイルでのみ fixture を明示的に使用
4. 環境変数の上書きコードを削除

## 次のアクション

1. ユーザーに推奨案を提示
2. 承認後、Issue #029 として実装開始
3. 段階的リファクタリング（既存テストを壊さない）

## 関連Issue

- Issue #026: PostgreSQL Docker セットアップ (完了)
- Issue #027: PostgreSQL 設定切り替え対応 (完了)
- Issue #029: テストアーキテクチャのリファクタリング (提案中)
