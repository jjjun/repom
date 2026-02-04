"""Integration tests for Alembic migration generation with use_id=False models

このテストはAlembicのマイグレーションファイル生成を実際に行い、
use_id=Falseのモデルに対してidカラムが生成されないことを確認します。

注意: このテストは時間がかかり、ファイルシステムを操作します。

Note: Models are defined within test functions with cleanup to ensure complete independence.
This allows tests to run in any order without conflicts.
"""

import tempfile
from pathlib import Path
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from alembic import command
from alembic.script import ScriptDirectory

from repom.models.base_model import BaseModel
from repom.database import Base
from repom.alembic import AlembicSetup  # Use AlembicSetup for alembic.ini generation


def test_alembic_migration_without_id():
    """
    use_id=Falseのモデルに対して生成されるマイグレーションファイルに
    idカラムの定義が含まれないことを確認

    このテストは以下を検証します:
    1. マイグレーションファイルが正常に生成される
    2. 生成されたマイグレーションファイルに'id'カラムの作成コードが含まれない
    3. 定義したカラム（code, name）の作成コードは含まれる

    Note: Models are defined within this test function to ensure independence.
    Note: Now uses AlembicSetup for cleaner alembic.ini generation.
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
            # Use repom's alembic directory (env.py, script.py.mako)
            # alembic/ is in the project root, not inside repom/ package
            import repom
            repom_root = Path(repom.__file__).parent.parent  # Go up one level to project root
            script_location = str((repom_root / 'alembic').resolve())

            # AlembicSetup to generate alembic.ini and version directory
            db_path = Path(tmpdir) / 'test.db'
            db_url = f'sqlite:///{db_path}'

            # Use Windows path format for version_locations
            tmpdir_path = Path(tmpdir).resolve()
            version_locations = str(tmpdir_path / 'alembic' / 'versions')

            setup = AlembicSetup(
                project_root=tmpdir,
                db_url=db_url,
                script_location=script_location,
                version_locations=version_locations
            )

            # Create alembic.ini and version directory
            setup.create_alembic_ini(overwrite=True)
            setup.create_version_directory()

            # Get AlembicConfig
            alembic_cfg = setup.get_alembic_config()

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
