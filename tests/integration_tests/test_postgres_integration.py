"""PostgreSQL integration tests - requires running PostgreSQL Docker container"""
from repom.config import config
import pytest
import os
from sqlalchemy import text
from sqlalchemy.exc import DataError

# PostgreSQL 統合テスト用に db_type を設定
# EXEC_ENV='test' のまま（repom_test データベースに接続）
POSTGRES_INTEGRATION_ENABLED = os.getenv('DB_TYPE') == 'postgres'


@pytest.mark.skipif(
    not POSTGRES_INTEGRATION_ENABLED,
    reason="PostgreSQL integration tests require DB_TYPE=postgres and running PostgreSQL container"
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
        assert str(engine.url.host) == config.postgres.host
        assert engine.url.port == config.postgres.port
        assert str(engine.url.username) == config.postgres.user
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

    def test_listjson_filter_element_and_empty_match(self):
        """listjson_filter() が PostgreSQL 上で要素一致・空リスト一致とも動作すること。
        json_each()/json_each_text() は配列を扱えず (cannot deconstruct an array
        as an object)、json_each() の value は json 型のため文字列との比較も
        できない (operator does not exist: json = character varying)。
        json_array_elements_text() / json_array_length() 経由の実装がこれらを
        回避することを確認する。"""
        from repom.database import get_sync_engine
        from repom.custom_types.ListJSON import ListJSON, listjson_filter
        from sqlalchemy import Column, Integer, MetaData, Table, select

        engine = get_sync_engine()
        metadata = MetaData()
        table = Table(
            "listjson_filter_integration_test",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("option_list", ListJSON),
        )

        with engine.begin() as conn:
            table.drop(conn, checkfirst=True)
            table.create(conn)
            try:
                conn.execute(
                    table.insert(),
                    [
                        {"option_list": ["foo", "bar"]},
                        {"option_list": ["baz", "qux"]},
                        {"option_list": []},
                    ],
                )

                filters = listjson_filter(table.c.option_list, ["foo"])
                rows = conn.execute(select(table).where(*filters)).fetchall()
                assert [row.option_list for row in rows] == [["foo", "bar"]]

                empty_filters = listjson_filter(table.c.option_list, [])
                empty_rows = conn.execute(select(table).where(*empty_filters)).fetchall()
                assert [row.option_list for row in empty_rows] == [[]]
            finally:
                table.drop(conn, checkfirst=True)

    def test_listjson_filter_duplicate_elements_do_not_duplicate_rows(self):
        """listjson_filter() が PostgreSQL 上でも重複した配列要素や複数の要求値で
        外側クエリの行を増やさないこと（repom#150）。相関 EXISTS を使う前は
        一致した要素の組み合わせごとに行が重複し、count() や LIMIT/OFFSET の
        ページングが壊れていた。"""
        from repom.database import get_sync_engine
        from repom.custom_types.ListJSON import ListJSON, listjson_filter
        from sqlalchemy import Column, Integer, MetaData, Table, func, select

        engine = get_sync_engine()
        metadata = MetaData()
        table = Table(
            "listjson_filter_duplicate_integration_test",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("option_list", ListJSON),
        )

        with engine.begin() as conn:
            table.drop(conn, checkfirst=True)
            table.create(conn)
            try:
                conn.execute(
                    table.insert(),
                    [
                        {"option_list": ["a", "a", "b", "b"]},
                        {"option_list": ["a", "b"]},
                        {"option_list": ["a"]},
                    ],
                )

                filters = listjson_filter(table.c.option_list, ["a", "b"])
                rows = conn.execute(select(table).where(*filters)).fetchall()
                assert sorted(row.option_list for row in rows) == [["a", "a", "b", "b"], ["a", "b"]]

                count = conn.execute(
                    select(func.count()).select_from(table).where(*filters)
                ).scalar()
                assert count == 2

                limited_rows = conn.execute(
                    select(table).where(*filters).order_by(table.c.id).limit(2)
                ).fetchall()
                assert len(limited_rows) == 2
            finally:
                table.drop(conn, checkfirst=True)

    def test_json_nul_escape_fails_on_text_extraction(self):
        from repom.database import get_sync_engine

        engine = get_sync_engine()

        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.execute(text("CREATE TEMP TABLE nul_json_test (payload json)"))
                conn.execute(
                    text("INSERT INTO nul_json_test (payload) VALUES (CAST(:payload AS json))"),
                    {'payload': '{"value":"\\u0000"}'},
                )

                with pytest.raises(DataError, match='unsupported Unicode escape sequence'):
                    conn.execute(text("SELECT payload ->> 'value' FROM nul_json_test"))
            finally:
                transaction.rollback()


@pytest.mark.skipif(
    not POSTGRES_INTEGRATION_ENABLED,
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
if POSTGRES_INTEGRATION_ENABLED:
    config.db_type = 'postgres'
    print_test_info()
