# Issue #027: PostgreSQL 設定切り替え対応

## ステータス
- **作成日**: 2026-02-01
- **優先度**: 高
- **複雑度**: 高
- **ステータス**: 📝 計画中

## 概要

repom の設定（`RepomConfig`）で PostgreSQL を選択できるようにし、`DB_TYPE` 環境変数で SQLite と PostgreSQL を切り替えられるようにする。
PostgreSQL 使用時は適切な接続設定とドライバーを使用するように実装する。

## 問題説明

現在、repom は SQLite 専用の設定になっており、PostgreSQL を使うには config を大幅にカスタマイズする必要がある。
データベース種別による切り替えを config に組み込むことで、外部プロジェクトでも簡単に PostgreSQL を使えるようにしたい。

## 期待される動作

```bash
# SQLite を使用（デフォルト）
DB_TYPE=sqlite poetry run alembic upgrade head

# PostgreSQL を使用
DB_TYPE=postgres poetry run alembic upgrade head
```

```python
# 環境変数で自動切り替え
from repom.config import config

# DB_TYPE=postgres の場合
# config.db_url => "postgresql+psycopg://repom:repom_dev@localhost:5432/repom_dev"

# DB_TYPE=sqlite の場合（デフォルト）
# config.db_url => "sqlite:///path/to/db.dev.sqlite3"
```

## 実装計画

### 1. config.py の拡張

```python
# repom/config.py に追加
@dataclass
class RepomConfig(Config):
    # ... 既存のフィールド ...
    
    # PostgreSQL サポート
    _db_type: Optional[str] = field(default=None, init=False, repr=False)
    _postgres_host: str = field(default='localhost', init=False, repr=False)
    _postgres_port: int = field(default=5432, init=False, repr=False)
    _postgres_user: str = field(default='repom', init=False, repr=False)
    _postgres_password: str = field(default='repom_dev', init=False, repr=False)
    _postgres_db: str = field(default='repom_dev', init=False, repr=False)
    
    @property
    def db_type(self) -> str:
        """データベースタイプ（sqlite/postgres）"""
        if self._db_type is not None:
            return self._db_type
        return os.getenv('DB_TYPE', 'sqlite')
    
    @db_type.setter
    def db_type(self, value: str):
        if value not in ('sqlite', 'postgres'):
            raise ValueError(f"Invalid DB_TYPE: {value}")
        self._db_type = value
    
    @property
    def postgres_host(self) -> str:
        return os.getenv('POSTGRES_HOST', self._postgres_host)
    
    @property
    def postgres_port(self) -> int:
        return int(os.getenv('POSTGRES_PORT', self._postgres_port))
    
    @property
    def postgres_user(self) -> str:
        return os.getenv('POSTGRES_USER', self._postgres_user)
    
    @property
    def postgres_password(self) -> str:
        return os.getenv('POSTGRES_PASSWORD', self._postgres_password)
    
    @property
    def postgres_db(self) -> str:
        """PostgreSQL データベース名（環境別）"""
        if self._postgres_db:
            return self._postgres_db
        
        # 環境別のデータベース名を返す
        env = self.exec_env
        base = os.getenv('POSTGRES_DB', 'repom')
        
        if env == 'test':
            return f"{base}_test"
        elif env == 'dev':
            return f"{base}_dev"
        elif env == 'prod':
            return base
        else:
            return f"{base}_dev"
    
    @property
    def db_url(self) -> Optional[str]:
        """データベースURL（SQLite/PostgreSQL 自動切り替え）"""
        if self._db_url is not None:
            return self._db_url
        
        # PostgreSQL
        if self.db_type == 'postgres':
            return (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        
        # SQLite（既存の実装）
        if self.exec_env == 'test' and self.use_in_memory_db_for_tests:
            return 'sqlite:///:memory:'
        
        if self.db_file:
            return f'sqlite:///{self.db_path}/{self.db_file}'
        return None
    
    @property
    def engine_kwargs(self) -> dict:
        """create_engine に渡す追加パラメータ（DB種別対応）"""
        # PostgreSQL
        if self.db_type == 'postgres':
            return {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True,
            }
        
        # SQLite（既存の実装）
        is_memory_db = self.db_url and ':memory:' in self.db_url
        
        if is_memory_db:
            from sqlalchemy.pool import StaticPool
            return {
                'poolclass': StaticPool,
                'connect_args': {'check_same_thread': False},
            }
        else:
            return {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True,
                'connect_args': {'check_same_thread': False}
            }
```

### 2. 依存関係の追加

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.12"
sqlalchemy = "^2.0"

# PostgreSQL サポート（オプショナル）
psycopg = {version = "^3.1", extras = ["binary"], optional = true}

[tool.poetry.extras]
postgres = ["psycopg"]
postgres-async = ["psycopg[binary,pool]"]
```

### 3. 環境変数設定

```bash
# .env ファイル
# データベースタイプ
DB_TYPE=postgres  # または 'sqlite'

# PostgreSQL 接続設定
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=repom
POSTGRES_PASSWORD=repom_dev
POSTGRES_DB=repom  # base name（環境別に _dev, _test が追加される）

# 実行環境
EXEC_ENV=dev
```

### 4. 外部プロジェクトでの使用例

```python
# mine-py/src/mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # PostgreSQL をデフォルトに
        self._db_type = 'postgres'
        
        # カスタム設定
        self._postgres_host = 'my-postgres-server'
        self._postgres_db = 'mine_py'

def get_repom_config():
    return MinePyConfig()
```

## テスト計画

### 単体テスト

```python
# tests/unit_tests/test_config_postgres.py
def test_config_db_url_postgres(monkeypatch):
    """PostgreSQL の db_url 生成をテスト"""
    monkeypatch.setenv('DB_TYPE', 'postgres')
    monkeypatch.setenv('EXEC_ENV', 'dev')
    
    from repom.config import RepomConfig
    config = RepomConfig()
    config.init()
    
    expected = "postgresql+psycopg://repom:repom_dev@localhost:5432/repom_dev"
    assert config.db_url == expected

def test_config_postgres_db_name_by_env(monkeypatch):
    """環境別の PostgreSQL DB名生成をテスト"""
    monkeypatch.setenv('DB_TYPE', 'postgres')
    
    config = RepomConfig()
    
    # dev 環境
    monkeypatch.setenv('EXEC_ENV', 'dev')
    assert config.postgres_db == 'repom_dev'
    
    # test 環境
    monkeypatch.setenv('EXEC_ENV', 'test')
    assert config.postgres_db == 'repom_test'
    
    # prod 環境
    monkeypatch.setenv('EXEC_ENV', 'prod')
    assert config.postgres_db == 'repom'

def test_config_engine_kwargs_postgres(monkeypatch):
    """PostgreSQL の engine_kwargs をテスト"""
    monkeypatch.setenv('DB_TYPE', 'postgres')
    
    config = RepomConfig()
    config.init()
    
    kwargs = config.engine_kwargs
    assert 'pool_size' in kwargs
    assert 'connect_args' not in kwargs  # SQLite 専用オプションがない
```

### 統合テスト

```python
# tests/integration_tests/test_postgres_connection.py
@pytest.mark.skipif(
    os.getenv('DB_TYPE') != 'postgres',
    reason="PostgreSQL tests require DB_TYPE=postgres"
)
def test_postgres_connection():
    """PostgreSQL への接続をテスト"""
    from repom.database import get_sync_engine
    from sqlalchemy import text
    
    engine = get_sync_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
```

### 手動テスト

```bash
# SQLite（デフォルト）
poetry run alembic upgrade head
poetry run pytest

# PostgreSQL
DB_TYPE=postgres poetry run postgres_start
DB_TYPE=postgres poetry run alembic upgrade head
DB_TYPE=postgres poetry run pytest
DB_TYPE=postgres poetry run postgres_stop
```

## 完了基準

- [ ] `RepomConfig` に PostgreSQL 関連プロパティが追加されている
- [ ] `db_type` プロパティで SQLite/PostgreSQL を切り替えられる
- [ ] `db_url` が DB種別に応じて適切な URL を返す
- [ ] `engine_kwargs` が DB種別に応じて適切な設定を返す
- [ ] 環境別の PostgreSQL データベース名が自動生成される
- [ ] `psycopg` が optional dependency として追加されている
- [ ] 単体テストがすべてパスする
- [ ] 統合テストが PostgreSQL で動作する
- [ ] SQLite のテストが引き続き動作する（後方互換性）
- [ ] ドキュメントが更新されている（README.md, config guide）

## 関連ドキュメント

- **Issue #026**: PostgreSQL Docker セットアップスクリプト
- **docs/guides/**: PostgreSQL 設定ガイド（作成予定）
- **README.md**: 環境変数セクション（更新予定）

## 依存関係

- **Issue #026**: Docker スクリプトが先に完成している必要がある

## 後方互換性

- デフォルトは `DB_TYPE=sqlite` のまま
- 既存の SQLite ユーザーには影響なし
- 環境変数を設定しない限り動作は変わらない

## マイグレーション対応

```bash
# SQLite から PostgreSQL へのデータ移行（別途手順が必要）
# 1. SQLite でデータをエクスポート
# 2. PostgreSQL でスキーマ作成
# 3. データをインポート
```

## 注意事項

- PostgreSQL 固有の機能（JSON型など）は別途対応が必要
- Alembic マイグレーションファイルは DB種別に依存しないように書く
- テストは SQLite と PostgreSQL 両方で実行することを推奨

---

**作成日**: 2026-02-01  
**最終更新**: 2026-02-01
