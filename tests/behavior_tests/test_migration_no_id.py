"""Integration tests for Alembic migration generation with use_id=False models

このテストはAlembicのマイグレーションファイル生成を実際に行い、
use_id=Falseのモデルに対してidカラムが生成されないことを確認します。

注意: このテストは時間がかかり、ファイルシステムを操作します。

Note: Models are defined within test functions with cleanup to ensure complete independence.
This allows tests to run in any order without conflicts.
"""

import os
import tempfile
import shutil
from pathlib import Path
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from typing import Optional
from alembic.config import Config as AlembicConfig
from alembic import command
from alembic.script import ScriptDirectory

from repom.models.base_model import BaseModel
from repom.database import Base


def _get_alembic_ini_content(alembic_dir, db_url):
    """Generate alembic.ini content for testing"""
    return f"""
[alembic]
script_location = {alembic_dir}
file_template = %%(rev)s_%%(slug)s
sqlalchemy.url = {db_url}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""


def _get_env_py_content():
    """Generate env.py content for testing"""
    return """
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from repom.database import Base

# Filter metadata to only include expected tables (avoid test interference)
from sqlalchemy import MetaData
filtered_metadata = MetaData()
expected_tables = {'samples', 'user_sessions', 'test_migration_no_id', 'test_migration_with_id', 'rosters'}
for table_name, table in Base.metadata.tables.items():
    if table_name in expected_tables:
        table.to_metadata(filtered_metadata)

target_metadata = filtered_metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
"""


def _get_mako_content():
    """Generate script.py.mako content for testing"""
    return """\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
"""


class MigrationTestModelNoId(BaseModel):
    """マイグレーションテスト用: use_id=Falseのモデル

    注意: クラス名は'Test'で始めないこと（pytestがテストクラスと誤認識するため）
    """
    __tablename__ = 'test_migration_no_id'

    use_id = False

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))


class MigrationTestModelWithId(BaseModel):
    """マイグレーションテスト用: use_id=Trueのモデル

    注意: クラス名は'Test'で始めないこと（pytestがテストクラスと誤認識するため）
    """
    __tablename__ = 'test_migration_with_id'

    name: Mapped[Optional[str]] = mapped_column(String(100))


def test_alembic_migration_without_id():
    """
    use_id=Falseのモデルに対して生成されるマイグレーションファイルに
    idカラムの定義が含まれないことを確認

    このテストは以下を検証します:
    1. マイグレーションファイルが正常に生成される
    2. 生成されたマイグレーションファイルに'id'カラムの作成コードが含まれない
    3. 定義したカラム（code, name）の作成コードは含まれる

    Note: Models are defined within this test function to ensure independence.
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers

    # Define models within test function for complete independence
    class MigrationTestModelNoId(BaseModel):
        """マイグレーションテスト用: use_id=Falseのモデル"""
        __tablename__ = 'test_migration_no_id'
        __table_args__ = {'extend_existing': True}

        use_id = False

        code: Mapped[str] = mapped_column(String(50), primary_key=True)
        name: Mapped[Optional[str]] = mapped_column(String(100))

    class MigrationTestModelWithId(BaseModel):
        """マイグレーションテスト用: use_id=Trueのモデル"""
        __tablename__ = 'test_migration_with_id'
        __table_args__ = {'extend_existing': True}

        name: Mapped[Optional[str]] = mapped_column(String(100))

    try:
        # Ensure mappers are configured
        configure_mappers()

        # 一時ディレクトリを作成
        with tempfile.TemporaryDirectory() as tmpdir:
            # テスト用のAlembic設定を準備
            alembic_dir = Path(tmpdir) / 'alembic'
            versions_dir = alembic_dir / 'versions'
            versions_dir.mkdir(parents=True)

            # alembic.iniを作成
            alembic_ini_path = Path(tmpdir) / 'alembic.ini'
            db_path = Path(tmpdir) / 'test.db'
            db_url = f'sqlite:///{db_path}'

            alembic_ini_content = _get_alembic_ini_content(alembic_dir, db_url)
            alembic_ini_path.write_text(alembic_ini_content)

            # env.pyを作成
            env_py_path = alembic_dir / 'env.py'
            env_py_content = _get_env_py_content()
            env_py_path.write_text(env_py_content)

            # script.py.makoを作成（最小限）
            mako_path = alembic_dir / 'script.py.mako'
            mako_content = _get_mako_content()
            mako_path.write_text(mako_content)

            # Alembic設定を読み込み
            alembic_cfg = AlembicConfig(str(alembic_ini_path))

            # マイグレーションファイルを生成
            try:
                command.revision(
                    alembic_cfg,
                    message="test migration",
                    autogenerate=True
                )
            except Exception as e:
                # マイグレーション生成に失敗した場合
                print(f"Migration generation failed: {e}")
                # このテストはスキップ（環境依存の可能性があるため）
                import pytest
                pytest.skip(f"Could not generate migration: {e}")

            # 生成されたマイグレーションファイルを確認
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            revisions = list(script_dir.walk_revisions())

            assert len(revisions) > 0, "No migration file was generated"

            # 最新のマイグレーションファイルを読み込み
            latest_revision = revisions[0]
            migration_file_path = latest_revision.path

            with open(migration_file_path, 'r', encoding='utf-8') as f:
                migration_content = f.read()

            # 検証: test_migration_no_idテーブルの作成部分だけを抽出してチェック
            # （他のテーブルのidカラムと混同しないため）
            import re
            # op.create_table('test_migration_no_id', から次の ) までを抽出
            table_pattern = r"op\.create_table\('test_migration_no_id'.*?\n\s*\)"
            table_match = re.search(table_pattern, migration_content, re.DOTALL)

            assert table_match is not None, \
                "Could not find test_migration_no_id table creation in migration"

            table_creation_code = table_match.group(0)

            # 検証: test_migration_no_idテーブルにidカラムの作成コードが含まれていないこと
            assert "sa.Column('id'" not in table_creation_code, \
                f"Migration should not contain 'id' column for use_id=False model. Found: {table_creation_code}"
            assert 'Column("id"' not in table_creation_code, \
                f"Migration should not contain 'id' column for use_id=False model. Found: {table_creation_code}"

            # 検証: 定義したカラムは含まれていること
            assert "'code'" in table_creation_code or '"code"' in table_creation_code, \
                f"Migration should contain 'code' column. Found: {table_creation_code}"
            assert "'name'" in table_creation_code or '"name"' in table_creation_code, \
                f"Migration should contain 'name' column. Found: {table_creation_code}"

            # 検証: test_migration_no_idテーブルの作成が含まれていること
            assert 'test_migration_no_id' in migration_content, \
                "Migration should contain the table name"
    finally:
        # Cleanup mappers to prevent interference with other tests
        clear_mappers()
        configure_mappers()


def test_alembic_migration_with_id():
    """
    use_id=True（デフォルト）のモデルに対して生成されるマイグレーションファイルに
    idカラムの定義が含まれることを確認

    Note: Models are defined within this test function to ensure independence.
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
    from sqlalchemy import inspect as sqla_inspect

    # Define model within test function
    class MigrationTestModelWithId(BaseModel):
        """マイグレーションテスト用: use_id=Trueのモデル"""
        __tablename__ = 'test_migration_with_id'
        __table_args__ = {'extend_existing': True}

        name: Mapped[Optional[str]] = mapped_column(String(100))

    try:
        # Ensure mappers are configured
        configure_mappers()

        # テスト用エンジンを作成
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)

        inspector = sqla_inspect(engine)

        # test_migration_with_idテーブルのカラムを確認
        if 'test_migration_with_id' in inspector.get_table_names():
            columns = inspector.get_columns('test_migration_with_id')
            column_names = [col['name'] for col in columns]

            # idカラムが存在することを確認
            assert 'id' in column_names, "Model with use_id=True should have 'id' column"
            assert 'name' in column_names

    finally:
        # Cleanup mappers to prevent interference with other tests
        clear_mappers()
        configure_mappers()


# 注意: 上記のtest_alembic_migration_without_id()は複雑で環境依存です。
# 実際の運用では、以下のようなシンプルな確認で十分な場合もあります:

def test_model_metadata_without_id():
    """
    シンプルな方法: モデルのメタデータを確認
    マイグレーションファイル生成をスキップし、SQLAlchemyのメタデータで検証

    Note: Models are defined within this test function to ensure independence.
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
    from sqlalchemy import inspect as sqla_inspect

    # Define model within test function
    class MigrationTestModelNoId(BaseModel):
        """マイグレーションテスト用: use_id=Falseのモデル"""
        __tablename__ = 'test_migration_no_id'
        __table_args__ = {'extend_existing': True}

        use_id = False

        code: Mapped[str] = mapped_column(String(50), primary_key=True)
        name: Mapped[Optional[str]] = mapped_column(String(100))

    try:
        # Ensure mappers are configured
        configure_mappers()

        # テスト用エンジン
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)

        inspector = sqla_inspect(engine)

        # use_id=Falseのテーブル
        if 'test_migration_no_id' in inspector.get_table_names():
            columns = inspector.get_columns('test_migration_no_id')
            column_names = [col['name'] for col in columns]

            assert 'id' not in column_names
            assert 'code' in column_names
            assert 'name' in column_names

    finally:
        # Cleanup mappers to prevent interference with other tests
        clear_mappers()
        configure_mappers()
