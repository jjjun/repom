# Testing Guide - repom

## 概要

repom は **Transaction Rollback パターン** と **インメモリDB** を採用し、高速かつ分離されたテスト環境を提供します。

**パフォーマンス**:
- 従来方式（DB再作成）: ~30秒
- Transaction Rollback: ~3秒
- **9倍の高速化を実現**

**インメモリDB（デフォルト）**:
- ✅ **35倍高速**: ファイルI/Oなし、純粋なメモリ操作
- ✅ **ロック防止**: "database is locked" エラーが発生しない
- ✅ **自動クリーンアップ**: プロセス終了時に自動削除

---

## 目次

- [基本的な使い方](#基本的な使い方)
- [インメモリDB設定](#インメモリdb設定)
- [外部プロジェクトでの使用](#外部プロジェクトでの使用)
- [テスト用DBの作成](#テスト用dbの作成)
- [モデルのインポート方法](#モデルのインポート方法)
- [トラブルシューティング](#トラブルシューティング)
- [ベストプラクティス](#ベストプラクティス)

---

## repom プロジェクト内でのテスト作成ガイドライン

### ⚠️ 重要：独自の fixture を定義しない

repom プロジェクト内でテストを書く場合、**テストファイル内で独自の `db_engine` や `db_session` fixture を定義してはいけません**。

**❌ 間違い**:
```python
# tests/unit_tests/test_my_feature.py

@pytest.fixture(scope='function')
def db_engine():  # ← conftest.py と衝突
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session

def test_my_feature(db_session):  # ← 独自の fixture を使ってしまう
    model = MyModel(name='Test')
    db_session.add(model)
    db_session.commit()
```

**問題点**:
1. `conftest.py` の `db_test` fixture と衝突
2. テーブルが作成されていない状態でクエリが実行される
3. BaseRepository が別のセッションを使うため、データが見えない

**✅ 正しい**:
```python
# tests/unit_tests/test_my_feature.py

def test_my_feature(db_test):  # ← conftest.py の db_test を使う
    model = MyModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    assert model.id is not None
```

### BaseRepository を使うテスト

BaseRepository を使う場合は、**必ず `session` パラメータに `db_test` を渡してください**。

**✅ 正しい**:
```python
def test_repository_integration(db_test):
    # データ作成
    model = MyModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    # Repository を使う（session を渡す）
    repo = MyRepository(MyModel, session=db_test)
    retrieved = repo.get_by_id(model.id)
    
    assert retrieved is not None
    assert retrieved.name == 'Test'
```

**❌ 間違い**:
```python
def test_repository_integration(db_test):
    model = MyModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    # ❌ session を渡していない
    repo = MyRepository(MyModel)
    retrieved = repo.get_by_id(model.id)
    # → None が返る（db_test のデータが見えない）
```

### get_by() の使い方

`BaseRepository.get_by()` は**位置引数形式**を使います：

```python
# ✅ 正しい
results = repo.get_by('name', 'Alice')

# ❌ 間違い
results = repo.get_by(name='Alice')  # TypeError
```

### トラブルシューティング："no such table" エラー

**症状**: `sqlite3.OperationalError: no such table: xxx`

**原因**: テストファイルで独自の fixture を定義し、`conftest.py` の `db_test` を使っていない

**解決方法**:
1. テストファイル内の `@pytest.fixture` 定義を削除
2. テスト関数のパラメータを `db_test` に変更
3. Repository 作成時に `session=db_test` を渡す

---

## 基本的な使い方

### repom プロジェクト内でのテスト

```python
# tests/conftest.py
import pytest
from repom.testing import create_test_fixtures

# テストフィクスチャを作成
db_engine, db_test = create_test_fixtures()
```

**実行**:
```bash
# すべてのテスト
poetry run pytest

# 特定のディレクトリ
poetry run pytest tests/unit_tests

# 詳細表示
poetry run pytest -v
```

---

## インメモリDB設定

### デフォルト動作（v0.x.x 以降）

repom は `exec_env == 'test'` の場合、自動的に SQLite インメモリDB (`sqlite:///:memory:`) を使用します：

```python
from repom.config import config

# test 環境では自動的にインメモリDB
config.exec_env = 'test'
print(config.db_url)
# 出力: sqlite:///:memory:
```

### インメモリDBを無効化する

ファイルベースのDB（`db.test.sqlite3`）を使用したい場合：

```python
# tests/conftest.py または設定ファイル
from repom.config import config

# conftest.py の pytest_configure() で設定
def pytest_configure(config_pytest):
    from repom.config import config as repom_config
    repom_config.use_in_memory_db_for_tests = False
```

または、外部プロジェクトの config_hook で：

```python
# mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        # ファイルベースのテストDBを使用
        self.use_in_memory_db_for_tests = False

def get_repom_config():
    return MinePyConfig()
```

```bash
# .env
CONFIG_HOOK=mine_py.config:get_repom_config
```

### どちらを使うべきか？

| 用途 | インメモリDB | ファイルベースDB |
|------|-------------|-----------------|
| **通常のユニットテスト** | ✅ 推奨（高速） | ❌ |
| **統合テスト** | ✅ 推奨 | △ |
| **DB永続化のテスト** | ❌ | ✅ 必要 |
| **複数プロセスでの並行テスト** | ⚠️ 各プロセス独立 | ✅ |
| **実行後のDB確認が必要** | ❌ | ✅ |
| **CI/CD環境** | ✅ 推奨 | △ |

**推奨**:
- 99%のケースで **インメモリDB**（デフォルト）で十分です
- ファイルベースDBは特別な理由がある場合のみ使用してください

---

## 外部プロジェクトでの使用

### パターン1: シンプルな構成（推奨）

外部プロジェクト（mine-py など）で repom を使用する場合：

```python
# tests/conftest.py
import os
import sys
from pathlib import Path
import pytest
from repom.testing import create_test_fixtures

def pytest_configure(config):
    """pytest 設定とパス設定"""
    # プロジェクトのルートディレクトリ
    root = Path(__file__).resolve().parents[1]
    src_path = root / 'src'
    
    # submodule のパス（必要に応じて）
    submodule_paths = (
        root / 'submod' / 'repom',
        root / 'submod' / 'mine_server',
    )
    
    # sys.path に追加
    for path in (root, src_path, *submodule_paths):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    
    # 環境変数の設定
    os.environ['EXEC_ENV'] = 'test'
    # プロジェクト固有の環境変数
    os.environ['PYMINE__CORE__ENV'] = 'test'


# ==================== Database Test Fixtures ====================

# repom のヘルパー関数でテストフィクスチャを作成
db_engine, db_test = create_test_fixtures()
```

**重要**: モデルのインポートは `create_test_fixtures()` が自動的に行います。

---

### パターン2: カスタムモデルローダー（高度な使用）

特殊なモデルインポート処理が必要な場合：

```python
# tests/conftest.py
import os
import sys
from pathlib import Path
import pytest
from repom.testing import create_test_fixtures

def pytest_configure(config):
    """pytest 設定"""
    root = Path(__file__).resolve().parents[1]
    src_path = root / 'src'
    
    for path in (root, src_path):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    
    os.environ['EXEC_ENV'] = 'test'


def custom_model_loader():
    """カスタムモデルローダー（特殊な処理が必要な場合）"""
    # 例: 特定の順序でモデルをインポート
    from myproject.models import base_models  # noqa: F401
    from myproject.models import user_models  # noqa: F401
    from myproject.models import task_models  # noqa: F401


# カスタムローダーを使用
db_engine, db_test = create_test_fixtures(
    model_loader=custom_model_loader
)
```

---

## テスト用DBの作成

### ❌ 間違い：Alembic でテスト用DB作成

```bash
# これは間違い
$env:EXEC_ENV='test'
poetry run alembic upgrade head  # テスト用DBには不要
poetry run pytest
```

**理由**:
- Alembic は**マイグレーション履歴の管理**が目的
- テストは**常に最新のモデル定義**を使うべき
- マイグレーション履歴の検証はテストの責任ではない

### ✅ 正しい：pytest が自動でDB作成

```bash
# これが正しい（DBは自動作成される）
poetry run pytest
```

**動作フロー**:
1. `pytest` コマンド実行
2. `conftest.py` が読み込まれる
3. `db_engine` フィクスチャが起動（session scope）
4. `create_test_fixtures()` 内で自動的にモデルをロード
5. `Base.metadata.create_all(bind=engine)` が実行される
6. 全テーブルが作成される
7. テスト実行
8. テスト終了後、自動でDB削除

### 手動でテスト用DB作成が必要な場合

通常は不要ですが、デバッグ目的で手動作成したい場合：

```powershell
# PowerShell
$env:EXEC_ENV='test'
poetry run db_create
```

```bash
# Unix系
export EXEC_ENV=test
poetry run db_create
```

---

## モデルのインポート方法

### ⚠️ 重要：外部キー制約エラーの回避

外部プロジェクトでテスト時に以下のエラーが発生する場合：

```
sqlalchemy.exc.NoReferencedTableError: 
Foreign key associated with column 'time_blocks.activity_id' 
could not find table 'time_activities'
```

**原因**: モデルの一部だけがインポートされ、外部キー参照先のテーブルが存在しない

### ❌ 間違い：手動でモデルをインポート

```python
# tests/conftest.py

# ❌ これは間違い
from src import models  # noqa: F401

db_engine, db_test = create_test_fixtures()
```

**問題点**:
- `src/models/__init__.py` の内容に依存
- すべてのモデルがインポートされる保証がない
- 外部キー参照が解決されない可能性がある

### ✅ 正しい方法1：CONFIG_HOOK を使用（推奨）

**Step 1: CONFIG_HOOK を設定**

```python
# myproject/config.py
from repom.config import MineDbConfig

class MyProjectConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        # 自動インポートするパッケージを指定
        self.model_locations = [
            'myproject.models',
            'repom.models'  # repom のモデルも必要な場合
        ]
        # セキュリティ: 許可するパッケージプレフィックス
        self.allowed_package_prefixes = {'myproject.', 'repom.'}

def get_repom_config():
    return MyProjectConfig()
```

**Step 2: 環境変数で指定**

```bash
# .env ファイル
CONFIG_HOOK=myproject.config:get_repom_config
```

**Step 3: conftest.py はシンプルに**

```python
# tests/conftest.py
import os
import sys
from pathlib import Path
from repom.testing import create_test_fixtures

def pytest_configure(config):
    # パス設定のみ
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    os.environ['EXEC_ENV'] = 'test'

# モデルは自動的にインポートされる
db_engine, db_test = create_test_fixtures()
```

**動作の仕組み**:
1. `create_test_fixtures()` が `load_set_model_hook_function()` を呼び出す
2. `load_models()` が実行される
3. `config.model_locations` に基づいて `auto_import_models_from_list()` が呼ばれる
4. すべてのモデルが自動的にインポートされる
5. 外部キー参照も正しく解決される

---

### ✅ 正しい方法2：カスタムモデルローダー

CONFIG_HOOK を使わない場合：

```python
# tests/conftest.py
import os
import sys
from pathlib import Path
from repom.testing import create_test_fixtures
from repom.utility import auto_import_models_from_list

def pytest_configure(config):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    os.environ['EXEC_ENV'] = 'test'


def load_all_models():
    """すべてのモデルを自動インポート"""
    auto_import_models_from_list(
        package_names=[
            'myproject.models',
            'repom.models'
        ],
        allowed_prefixes={'myproject.', 'repom.'}
    )


# カスタムローダーを使用
db_engine, db_test = create_test_fixtures(
    model_loader=load_all_models
)
```

---

### ✅ 正しい方法3：明示的にすべてインポート（非推奨）

最もシンプルですが、メンテナンス性が低い：

```python
# tests/conftest.py
import os
import sys
from pathlib import Path
from repom.testing import create_test_fixtures

def pytest_configure(config):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    os.environ['EXEC_ENV'] = 'test'


def load_all_models():
    """すべてのモデルを明示的にインポート"""
    # すべてのモデルファイルを明示的にインポート
    from myproject.models import user  # noqa: F401
    from myproject.models import task  # noqa: F401
    from myproject.models import activity  # noqa: F401
    from myproject.models import time_block  # noqa: F401
    # ... すべてのモデルファイル


db_engine, db_test = create_test_fixtures(
    model_loader=load_all_models
)
```

**デメリット**:
- 新しいモデルを追加するたびに更新が必要
- インポートの順序に依存する可能性がある

---

## トラブルシューティング

### NoReferencedTableError が発生する

**エラー例**:
```
sqlalchemy.exc.NoReferencedTableError: 
Foreign key associated with column 'time_blocks.activity_id' 
could not find table 'time_activities'
```

**原因**: 外部キー参照先のモデルがインポートされていない

**解決方法**:
1. **CONFIG_HOOK を使用**（推奨）
   - `config.model_locations` にパッケージを指定
   - `auto_import_models` が自動的にすべてのモデルをインポート

2. **カスタムモデルローダー**
   - `auto_import_models_from_list()` を使用
   - すべてのモデルパッケージを指定

3. **デバッグ方法**
   ```python
   # テスト前にモデルが登録されているか確認
   from repom.db import Base
   print(Base.metadata.tables.keys())
   # dict_keys(['users', 'tasks', 'time_activities', 'time_blocks', ...])
   ```

---

### ImportError: No module named '...'

**原因**: `sys.path` にパスが追加されていない

**解決方法**:
```python
# tests/conftest.py
def pytest_configure(config):
    root = Path(__file__).resolve().parents[1]
    src_path = root / 'src'
    
    # 重要: insert(0, ...) で先頭に追加
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(src_path))
```

---

### テストが遅い

**症状**: 195テストで30秒以上かかる

**原因**: Transaction Rollback パターンを使用していない

**解決方法**:
```python
# tests/conftest.py

# ❌ 古い方式（各テストでDB再作成）
@pytest.fixture()
def db_test():
    engine = create_engine(config.db_url)
    Base.metadata.create_all(bind=engine)  # 毎回作成
    # ...
    Base.metadata.drop_all(bind=engine)  # 毎回削除

# ✅ 新しい方式（Transaction Rollback）
from repom.testing import create_test_fixtures
db_engine, db_test = create_test_fixtures()
```

---

### WARNING: transaction already deassociated

**症状**: 例外が発生するテストで警告が出る

**解決方法**: 既に修正済み（`repom/testing.py` の `transaction.is_active` チェック）

最新版の `repom` を使用してください。

---

### 「no such table」エラー（repom.session や repom.db を使用する場合）

**症状**: `get_db_session()` や `repom.db.engine` を使用するテストで「no such table」エラーが発生

**エラー例**:
```python
# tests/unit_tests/test_session.py
from repom.session import get_db_session  # ← モジュールレベルでインポート

def test_something(db_test):
    gen = get_db_session()
    session = next(gen)
    # OperationalError: no such table: my_table
```

**原因**: 
1. `repom.session` や `repom.db` がモジュールレベルで `engine` を作成
2. インポート時点で `EXEC_ENV` が設定されていないため、dev 環境のDBを参照
3. `conftest.py` の `db_test` フィクスチャとは異なる engine のため、テーブルが作成されていない

**解決方法 1: テストファイルの先頭で EXEC_ENV を設定** ⭐ 推奨

```python
# tests/unit_tests/test_session.py
import os
import pytest

# CRITICAL: repom モジュールをインポートする前に設定
os.environ['EXEC_ENV'] = 'test'

from repom.session import get_db_session  # ← この時点で :memory: DB が使われる
```

**解決方法 2: repom.db.engine を直接使わない**

```python
# ❌ 間違い: repom.db.engine を直接使用
from repom.db import engine
inspector = inspect(engine)

# ✅ 正しい: db_test fixture の engine を使用
def test_something(db_test):
    inspector = inspect(db_test.bind)
```

**ポイント**:
- テストファイルで `repom.session`, `repom.db`, `repom.async_session` などをインポートする場合
- **必ずインポート前に `os.environ['EXEC_ENV'] = 'test'` を設定する**
- または、`db_test.bind` を使って fixture の engine を参照する

---

### StaticPool 環境でのトランザクション分離の制限

**症状**: `:memory:` + `StaticPool` 環境で、コミットしていないデータが別のセッションで見える

**原因**: 
- `StaticPool` は単一の接続を全スレッド/セッションで共有
- トランザクション分離が完全には機能しない

**対処方法**:

```python
# このようなテストは :memory: + StaticPool では正しく動作しない
@pytest.mark.skipif(
    config.db_url == 'sqlite:///:memory:',
    reason="StaticPool does not fully support transaction isolation"
)
def test_session_isolation(db_test):
    """セッションの独立性をテスト（ファイルベースDBのみ）"""
    # ...
```

**ポイント**:
- トランザクション分離をテストしたい場合は、ファイルベースDBを使用
- 通常のテストでは `:memory:` + `StaticPool` で問題なし

---

## ベストプラクティス

### 1. CONFIG_HOOK を使用する（推奨）

```python
# myproject/config.py
class MyProjectConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        self.model_locations = ['myproject.models']
        self.allowed_package_prefixes = {'myproject.', 'repom.'}

# .env
CONFIG_HOOK=myproject.config:get_repom_config
```

**メリット**:
- モデルのインポート漏れがない
- 新しいモデルを追加しても自動的にインポートされる
- テスト以外（DB作成、マイグレーション）でも同じ設定を使用

---

### 2. シンプルな conftest.py

```python
# tests/conftest.py
import os
import sys
from pathlib import Path
from repom.testing import create_test_fixtures

def pytest_configure(config):
    """最小限のパス設定のみ"""
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    os.environ['EXEC_ENV'] = 'test'

# これだけ！
db_engine, db_test = create_test_fixtures()
```

**メリット**:
- シンプルで理解しやすい
- メンテナンスが容易
- 別のAIエージェントも理解できる

---

### 3. テストは pytest だけで完結

```bash
# ✅ Good: これだけでOK
poetry run pytest

# ❌ Bad: 不要な前処理
poetry run alembic upgrade head  # 不要
poetry run db_create             # 不要
poetry run pytest
```

---

### 4. 環境変数は pytest_configure で設定

```python
def pytest_configure(config):
    """テスト開始前に一度だけ実行される"""
    os.environ['EXEC_ENV'] = 'test'
    os.environ['CONFIG_HOOK'] = 'myproject.config:get_repom_config'
```

**メリット**:
- コマンドラインで環境変数を設定する必要がない
- `poetry run pytest` だけで実行可能

---

## まとめ

### テスト用DB作成の正解

| 質問 | 回答 |
|------|------|
| **Alembic でテスト用DB作成？** | ❌ 不要（間違い） |
| **db_create コマンドが必要？** | ❌ 通常は不要 |
| **pytest 実行だけでOK？** | ✅ 正解 |
| **モデルのインポート方法は？** | ✅ CONFIG_HOOK + `model_locations`（推奨） |

### 外部キーエラーの解決

| 方法 | 推奨度 | 理由 |
|------|--------|------|
| **CONFIG_HOOK + model_locations** | ⭐⭐⭐⭐⭐ | 自動、安全、メンテナンス不要 |
| **カスタムモデルローダー + auto_import** | ⭐⭐⭐⭐ | 柔軟、手動設定が必要 |
| **明示的インポート** | ⭐⭐ | メンテナンス性が低い |
| **`from src import models`** | ❌ | 不完全、エラーが発生しやすい |

---

## 🔄 非同期テスト（Async Support）

FastAPI Users など async ライブラリのテストには `create_async_test_fixtures()` を使用します。

### 基本的な使い方

```python
# tests/conftest.py
from repom.testing import create_test_fixtures, create_async_test_fixtures

# 同期版（既存）
db_engine, db_test = create_test_fixtures()

# async 版（新規）
async_db_engine, async_db_test = create_async_test_fixtures()
```

### async テストの作成

```python
import pytest
from sqlalchemy import select

@pytest.mark.asyncio
async def test_create_user(async_db_test):
    """async Session を使用したテスト"""
    from your_project.models import User
    
    # ユーザー作成
    user = User(email="test@example.com", hashed_password="hashed")
    async_db_test.add(user)
    await async_db_test.flush()
    
    # 取得
    stmt = select(User).where(User.email == "test@example.com")
    result = await async_db_test.execute(stmt)
    found_user = result.scalar_one_or_none()
    
    assert found_user is not None
    assert found_user.email == "test@example.com"
```

### 依存関係のインストール

```bash
# SQLite async サポート
poetry add repom[async]

# PostgreSQL async サポート
poetry add repom[postgres-async]

# 両方サポート
poetry add repom[async-all]

# pytest-asyncio も必要
poetry add --group dev pytest-asyncio
```

### FastAPI Users との統合例

```python
@pytest.mark.asyncio
async def test_fastapi_users_registration(async_db_test):
    """FastAPI Users を使用した認証テスト"""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from your_project.models import User
    
    # FastAPI Users の UserDatabase を作成
    user_db = SQLAlchemyUserDatabase(async_db_test, User)
    
    # ユーザー登録
    user_dict = {
        "email": "newuser@example.com",
        "hashed_password": "hashed_password",
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
    }
    user = await user_db.create(user_dict)
    
    # 確認
    assert user.email == "newuser@example.com"
    
    # メールで検索
    found = await user_db.get_by_email("newuser@example.com")
    assert found is not None
```

### Transaction Rollback の動作

async テストでも同じ Transaction Rollback パターンが動作します：

```python
@pytest.mark.asyncio
async def test_first_test(async_db_test):
    """最初のテストでデータを追加"""
    user = User(email="test1@example.com")
    async_db_test.add(user)
    await async_db_test.flush()
    # テスト終了時に自動ロールバック

@pytest.mark.asyncio
async def test_second_test(async_db_test):
    """2番目のテストでは前のデータが残っていない"""
    from sqlalchemy import select
    
    stmt = select(User).where(User.email == "test1@example.com")
    result = await async_db_test.execute(stmt)
    found = result.scalar_one_or_none()
    
    assert found is None  # ロールバックされている
```

### 重要な注意事項

#### 1. Lazy Loading は使えない

```python
# ❌ 動作しない
user = await async_db_test.get(User, 1)
posts = user.posts  # AttributeError

# ✅ Eager Loading を使用
from sqlalchemy.orm import selectinload

stmt = select(User).options(selectinload(User.posts)).where(User.id == 1)
result = await async_db_test.execute(stmt)
user = result.scalar_one()
posts = user.posts  # OK
```

#### 2. await を忘れずに

```python
# ❌ await を忘れる
result = async_db_test.execute(stmt)  # TypeError

# ✅ await を付ける
result = await async_db_test.execute(stmt)
```

#### 3. URI 変換が自動で行われる

```python
# 同期 URI
sqlite:///data/db.test.sqlite3

# async URI（自動変換される）
sqlite+aiosqlite:///data/db.test.sqlite3
```

### パフォーマンス

async テストでも高速性は維持されます：

- **DB作成**: session scope で1回のみ
- **各テスト**: Transaction Rollback のみ
- **速度**: 同期テストと同等の高速性

---

## 関連ドキュメント

- **repom/testing.py**: `create_test_fixtures()` / `create_async_test_fixtures()` の実装
- **docs/guides/auto_import_models_guide.md**: モデル自動インポートの詳細
- **README.md**: テスト戦略セクション
- **AGENTS.md**: Testing Framework セクション

---

**最終更新**: 2025-12-14
