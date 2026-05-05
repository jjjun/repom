# Issue #047: DB名プレフィックスのカスタマイズ対応

**ステータス**: ✅ 完了

**作成日**: 2026-02-24

**完了日**: 2026-02-24

**優先度**: 中

## 問題の説明

現状、PostgreSQL と SQLite のデータベース名に使用されるプレフィックスがハードコードされており、外部プロジェクトでカスタマイズできない。

### 現状の実装

**PostgreSQL** ([config.py#L268-287](../../../repom/config.py#L268)):
```python
@property
def postgres_db(self) -> str:
    if self.postgres.database is not None:
        return self.postgres.database  # 完全上書き

    base = 'repom'  # ← ハードコード
    env = self.exec_env
    ...
```

**SQLite** ([config.py#L176-180](../../../repom/config.py#L176)):
```python
def get_default_db_file(self, exec_env: str) -> str:
    if exec_env in ("test", "dev"):
        return f"db.{exec_env}.sqlite3"  # ← "db" がハードコード
    return "db.sqlite3"
```

### 現在の動作

| 環境 | PostgreSQL | SQLite |
|------|-----------|--------|
| dev  | `repom_dev` | `db.dev.sqlite3` |
| test | `repom_test` | `db.test.sqlite3` または `:memory:` |
| prod | `repom` | `db.sqlite3` |

### 問題点

1. **PostgreSQL**: `postgres.database` を設定すると環境別サフィックスが無効になる
2. **SQLite**: プレフィックス変更の手段がない（`db_file` で完全上書きするしかない）
3. **一貫性**: PostgreSQL と SQLite で設定方法が異なる

## 提案される解決策

`RepomConfig` に `db_name` プロパティを追加し、両方の DB 名プレフィックスとして使用する。

> **Note**: `package_name` はフック識別用（`if config.package_name == 'repom':`）なので流用不可。

### 変更後の動作

| 環境 | PostgreSQL | SQLite |
|------|-----------|--------|
| dev  | `{db_name}_dev` | `{db_name}_dev.sqlite3` |
| test | `{db_name}_test` | `{db_name}_test.sqlite3` |
| prod | `{db_name}` | `{db_name}.sqlite3` |

### 実装案

**RepomConfig に `db_name` プロパティ追加** (`config.py`):
```python
# フィールド追加
_db_name: Optional[str] = field(default=None, init=False, repr=False)

@property
def db_name(self) -> str:
    """DB名のベース（デフォルト: repom）
    
    PostgreSQL: {db_name}_dev, {db_name}_test, {db_name}
    SQLite: {db_name}.dev.sqlite3, {db_name}.test.sqlite3, {db_name}.sqlite3
    """
    return self._db_name or "repom"

@db_name.setter
def db_name(self, value: str):
    self._db_name = value
```

**PostgreSQL** (`config.py`):
```python
@property
def postgres_db(self) -> str:
    if self.postgres.database is not None:
        return self.postgres.database  # 完全上書き（優先）

    base = self.db_name  # db_name を使用
    env = self.exec_env

    if env == 'test':
        return f"{base}_test"
    elif env == 'dev':
        return f"{base}_dev"
    return base
```

**SQLite** (`config.py`):
```python
def get_default_db_file(self, exec_env: str) -> str:
    prefix = self._config.db_name if self._config else "db"
    if exec_env in ("test", "dev"):
        return f"{prefix}_{exec_env}.sqlite3"
    return f"{prefix}.sqlite3"
```

### 使用例

```python
# mine-py/config.py
def hook_config(config):
    if config.package_name == 'mine_py':
        config.db_name = 'mine_py'
        config.db_type = 'postgres'
    return config

# 結果:
# dev  → mine_py_dev (PostgreSQL) / mine_py_dev.sqlite3 (SQLite)
# test → mine_py_test / mine_py_test.sqlite3
# prod → mine_py / mine_py.sqlite3
```

### 優先順位

1. `postgres.database` / `sqlite.db_file` が設定されていれば、それを使用（完全上書き）
2. そうでなければ `db_name` + 環境サフィックス

## 影響範囲

- `repom/config.py`: `db_name` プロパティ追加、`postgres_db` 修正、`SqliteConfig.get_default_db_file()` 修正
- `repom/postgres/manage.py`: `generate_init_sql()` を `db_name` を使用するよう修正
- `repom/config_hook.py`: `config.postgres.database = "repom"` の削除（不要になる）
- テスト: DB 名関連のテスト追加

### PostgreSQL DB 作成スクリプトの修正

現在の `generate_init_sql()` ([postgres/manage.py#L209-228](../../../repom/postgres/manage.py#L209)):
```python
def generate_init_sql() -> str:
    base = config.postgres.database or "repom"  # ← ハードコード
    user = config.postgres.user

    return f"""-- {base} project databases
CREATE DATABASE {base}_dev;
CREATE DATABASE {base}_test;
CREATE DATABASE {base}_prod;  # ← _prod サフィックスあり（postgres_db と不整合）
...
```

修正後:
```python
def generate_init_sql() -> str:
    base = config.db_name  # db_name を使用
    user = config.postgres.user

    return f"""-- {base} project databases
CREATE DATABASE {base};       # prod（サフィックスなし）
CREATE DATABASE {base}_dev;
CREATE DATABASE {base}_test;

GRANT ALL PRIVILEGES ON DATABASE {base} TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_dev TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_test TO {user};
"""
```

> **Note**: `postgres_db` プロパティでは prod 環境は `{db_name}` (サフィックスなし) なので、`_prod` は不要。

## 実装計画

1. `RepomConfig` に `db_name` プロパティ追加（L210付近）
2. `SqliteConfig.get_default_db_file()` を修正し `db_name` を使用（L176-180）
3. `RepomConfig.postgres_db` を修正し `db_name` を使用（L295）
4. `postgres/manage.py` の修正:
   - `generate_init_sql()`: `db_name` を使用、`_prod` を削除（L217-228）
   - `generate_pgadmin_servers_json()`: `db_name` を使用（L120）
   - `print_connection_info()`: 動的に DB 名を表示（L85）
5. `config_hook.py` から `config.postgres.database = "repom"` を削除
6. 単体テスト追加
7. ドキュメント更新

## テスト計画

```python
def test_db_name_default():
    config = RepomConfig()
    assert config.db_name == 'repom'

def test_postgres_db_uses_db_name():
    config = RepomConfig()
    config.db_name = 'myapp'
    config._exec_env = 'dev'
    assert config.postgres_db == 'myapp_dev'

def test_postgres_database_overrides_db_name():
    config = RepomConfig()
    config.db_name = 'myapp'
    config.postgres.database = 'custom_db'
    assert config.postgres_db == 'custom_db'

def test_sqlite_db_file_uses_db_name():
    config = RepomConfig()
    config.db_name = 'myapp'
    config._exec_env = 'dev'
    assert 'myapp_dev.sqlite3' in config.db_url

def test_generate_init_sql_uses_db_name():
    # db_name を設定した場合、init.sql に反映される
    config.db_name = 'myapp'
    sql = generate_init_sql()
    assert 'CREATE DATABASE myapp;' in sql
    assert 'CREATE DATABASE myapp_dev;' in sql
    assert 'CREATE DATABASE myapp_test;' in sql
```

## 後方互換性

- デフォルトの `db_name = "repom"` により、既存の動作は維持される
- `postgres.database` / `sqlite.db_file` による完全上書きも引き続きサポート

## 関連リソース

- [config.py](../../../repom/config.py)
- [config_hook.py](../../../repom/config_hook.py)
- [postgres/manage.py](../../../repom/postgres/manage.py)
- [Issue #027: PostgreSQL 設定統合](../completed/027_postgresql_config_integration.md)

---

## 詳細な影響範囲調査

### 1. repom/config.py

| 行 | 現在 | 修正後 |
|----|------|--------|
| L295 | `base = 'repom'` | `base = self.db_name` |
| L176-180 | `get_default_db_file()` で `"db"` をハードコード | `self._config.db_name` を使用 |

### 2. repom/postgres/manage.py

| 行 | 現在 | 修正後 |
|----|------|--------|
| L85 | `print(f"  Databases: repom_dev, repom_test, repom_prod")` | `db_name` を使った動的出力 |
| L120 | `base_db = config.postgres.database or "repom"` | `base_db = config.db_name` |
| L217 | `base = config.postgres.database or "repom"` | `base = config.db_name` |
| L221-223 | `{base}_prod` を作成 | `{base}` (prod サフィックスなし) に修正 |

### 3. repom/config_hook.py

| 行 | 現在 | 修正後 |
|----|------|--------|
| L40 | `config.postgres.database = "repom"` | 削除（不要） |

### 4. テストファイル（影響あり）

以下のテストファイルは `db_name` のデフォルト値 `"repom"` を使用する前提なので、**修正不要**（デフォルト値で動作）：

- `tests/unit_tests/test_postgres_manage.py`
  - L175-190: `generate_init_sql()` のテスト - デフォルト値テストはそのまま動作
  - L319: `MaintenanceDB` のテスト - デフォルト値で動作
  
- `tests/unit_tests/test_repom_info.py`
  - L278, L320: mock で db_url を設定しているので影響なし

- `tests/unit_tests/test_docker_compose.py`
  - L226: サンプルの environment 値（実装には影響なし）

### 5. ドキュメント

- `docs/guides/features/config_hook_guide.md`: `db_name` の使用例を追加
- `docs/guides/postgresql/postgresql_setup_guide.md`: `db_name` 設定の説明追加
