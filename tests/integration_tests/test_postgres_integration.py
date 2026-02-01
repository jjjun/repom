"""PostgreSQL integration tests - requires running PostgreSQL Docker container"""
from repom.config import config
import pytest
import os
from sqlalchemy import text

# conftest.py が EXEC_ENV='test' を設定するため、PostgreSQL 統合テスト用に 'dev' に変更
os.environ['EXEC_ENV'] = 'dev'

# PostgreSQL 統合テスト用に db_type を設定
config.db_type = 'postgres'


@pytest.mark.skipif(
    config.db_type != 'postgres',
    reason="PostgreSQL integration tests require config.db_type='postgres' and running PostgreSQL container"
)
class TestPostgreSQLIntegration:
    """PostgreSQL への実際の接続テスト"""

    def test_connection_basic(self):
        """PostgreSQL への基本的な接続"""
        from repom.database import get_sync_engine

        engine = get_sync_engine()

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as num"))
            assert result.scalar() == 1

    def test_connection_version(self):
        """PostgreSQL バージョン確認"""
        from repom.database import get_sync_engine

        engine = get_sync_engine()

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            assert 'PostgreSQL' in version
            print(f"\nPostgreSQL Version: {version}")

    def test_database_name(self):
        """接続先データベース名の確認"""
        from repom.database import get_sync_engine
        from repom.config import config

        engine = get_sync_engine()

        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()

            # config の postgres_db と一致するか確認
            assert db_name == config.postgres_db
            print(f"\nConnected to database: {db_name}")

    def test_create_table(self):
        """テーブル作成・挿入・検索のテスト"""
        from repom.database import get_sync_engine
        from sqlalchemy import text

        engine = get_sync_engine()

        with engine.begin() as conn:
            # テーブル作成
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS integration_test (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # データ挿入
            conn.execute(
                text("INSERT INTO integration_test (name) VALUES (:name)"),
                {"name": "test_user"}
            )

            # データ検索
            result = conn.execute(
                text("SELECT name FROM integration_test WHERE name = :name"),
                {"name": "test_user"}
            )
            name = result.scalar()
            assert name == "test_user"

            # クリーンアップ
            conn.execute(text("DROP TABLE integration_test"))

    def test_config_url_matches_connection(self):
        """config.db_url が実際の接続に使われているか確認"""
        from repom.config import config
        from repom.database import get_sync_engine

        # config.db_url を確認
        db_url = config.db_url
        assert db_url.startswith('postgresql+psycopg://')

        # engine が正しく作成されているか
        engine = get_sync_engine()
        assert engine.url.drivername == 'postgresql+psycopg'
        assert str(engine.url.host) == config.postgres_host
        assert engine.url.port == config.postgres_port
        assert str(engine.url.username) == config.postgres_user
        assert str(engine.url.database) == config.postgres_db

    def test_connection_pool_settings(self):
        """接続プール設定の確認"""
        from repom.database import get_sync_engine

        engine = get_sync_engine()

        # Pool の設定を確認
        assert engine.pool.size() == 10  # pool_size
        # max_overflow は内部的に管理されているため直接確認できない

        # 実際に複数接続を作成してプールが動作するか確認
        connections = []
        try:
            for i in range(5):
                conn = engine.connect()
                connections.append(conn)

            # すべての接続が正常に作成された
            assert len(connections) == 5
        finally:
            # クリーンアップ
            for conn in connections:
                conn.close()


@pytest.mark.skipif(
    os.getenv('DB_TYPE') != 'postgres',
    reason="PostgreSQL integration tests require DB_TYPE=postgres"
)
class TestPostgreSQLModelOperations:
    """PostgreSQL での BaseModel 操作テスト"""

    def test_basemodel_crud(self, db_test):
        """BaseModel を使った CRUD 操作"""
        from repom.examples.models import SampleModel
        from repom import BaseRepository

        repo = BaseRepository(SampleModel, db_test)

        # Create
        sample = SampleModel(value="PostgreSQL Test")
        saved = repo.save(sample)
        db_test.flush()

        assert saved.id is not None
        assert saved.value == "PostgreSQL Test"

        # Read
        found = repo.get_by_id(saved.id)
        assert found is not None
        assert found.value == "PostgreSQL Test"

        # Update
        found.value = "Updated value"
        updated = repo.save(found)
        db_test.flush()
        assert updated.value == "Updated value"

        # Delete
        repo.remove(updated)
        db_test.flush()

        deleted = repo.get_by_id(updated.id)
        assert deleted is None


def print_test_info():
    """テスト情報を表示"""
    import os
    from repom.config import config

    print("\n" + "="*60)
    print("PostgreSQL Integration Test Information")
    print("="*60)
    print(f"EXEC_ENV: {os.getenv('EXEC_ENV', 'not set')}")
    print(f"Config DB Type: {config.db_type}")
    print(f"Config DB URL: {config.db_url}")
    print(f"PostgreSQL Database: {config.postgres_db}")
    print("="*60 + "\n")


# テスト実行前に情報表示
if config.db_type == 'postgres':
    print_test_info()
