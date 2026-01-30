"""
詳細調査: TYPE_CHECKING と auto_import_models の関係

このテストでは、以下を詳しく調査します:
1. auto_import_models がどの順序でモデルをインポートするか
2. TYPE_CHECKING ブロック内のインポートが実行時にどう扱われるか
3. SQLAlchemy がいつ名前解決を行うか
4. 実際にエラーが発生するケースは何か
"""

import sys
import tempfile
import shutil
import warnings
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest


def test_inspect_import_order():
    """
    import_from_directory のインポート順序を確認
    """
    # 一時ディレクトリ作成
    temp_dir = Path(tempfile.mkdtemp(prefix="test_order_"))

    try:
        # テストモデルディレクトリを作成
        models_dir = temp_dir / "test_order"
        models_dir.mkdir(parents=True)

        # __init__.py
        (models_dir / "__init__.py").write_text("", encoding='utf-8')

        # 複数のファイルを作成してインポート順序を確認
        files = [
            "a_model.py",
            "z_model.py",
            "m_model.py",
            "b_model.py",
        ]

        for filename in files:
            (models_dir / filename).write_text(f"""
print(f"Importing: {filename}")

from repom.models.base_model_auto import BaseModelAuto
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

class {filename[:-3].title().replace('_', '')}Model(BaseModelAuto):
    __tablename__ = '{filename[:-3]}'
    name: Mapped[str] = mapped_column(String(50))
""", encoding='utf-8')

        # sys.path に追加
        sys.path.insert(0, str(temp_dir))

        try:
            from repom._.discovery import import_from_directory

            print("\n=== Testing import order ===")
            import_from_directory(
                directory=models_dir,
                base_package='test_order'
            )
            print("=== Import complete ===\n")

            # 期待される順序: a_model, b_model, m_model, z_model (アルファベット順)

        finally:
            # クリーンアップ
            if str(temp_dir) in sys.path:
                sys.path.remove(str(temp_dir))
            modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_order')]
            for module in modules_to_remove:
                del sys.modules[module]
            from repom.models.base_model import BaseModel
            BaseModel.metadata.clear()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sqlalchemy_relationship_lazy_resolution(isolated_mapper_registry):
    """
    SQLAlchemy の relationship がいつ名前解決を行うかを確認

    重要な発見:
    - relationship() 呼び出し時には名前解決しない
    - マッパー設定時（mapper configuration）に名前解決する
    - マッパー設定は以下のタイミングで起こる:
      1. 最初のクエリ実行時
      2. metadata.create_all() 実行時
      3. 明示的に configure_mappers() を呼び出した時

    Note:
    - isolated_mapper_registry フィクスチャにより、テスト終了後に自動クリーンアップ
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="test_lazy_"))

    try:
        models_dir = temp_dir / "test_lazy"
        models_dir.mkdir(parents=True)

        (models_dir / "__init__.py").write_text("", encoding='utf-8')

        # Parent model (アルファベット順で先)
        (models_dir / "a_parent.py").write_text("""
from typing import TYPE_CHECKING, List
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import String
from repom.models.base_model_auto import BaseModelAuto

if TYPE_CHECKING:
    from .z_child import ZChildModel

print(">>> a_parent.py: Defining AParentModel")

class AParentModel(BaseModelAuto):
    __tablename__ = 'a_parents'
    name: Mapped[str] = mapped_column(String(50))
    
    # この時点では ZChildModel は存在しない
    children: Mapped[List["ZChildModel"]] = relationship(
        back_populates="parent"
    )

print(">>> a_parent.py: AParentModel defined successfully")
""", encoding='utf-8')

        # Child model (アルファベット順で後)
        (models_dir / "z_child.py").write_text("""
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

if TYPE_CHECKING:
    from .a_parent import AParentModel

print(">>> z_child.py: Defining ZChildModel")

class ZChildModel(BaseModelAuto):
    __tablename__ = 'z_children'
    name: Mapped[str] = mapped_column(String(50))
    parent_id: Mapped[int] = mapped_column(ForeignKey('a_parents.id'))
    
    parent: Mapped["AParentModel"] = relationship(
        back_populates="children"
    )

print(">>> z_child.py: ZChildModel defined successfully")
""", encoding='utf-8')

        sys.path.insert(0, str(temp_dir))

        try:
            from repom._.discovery import import_from_directory
            from sqlalchemy.orm import configure_mappers

            print("\n" + "=" * 80)
            print("STEP 1: import_from_directory (インポートのみ)")
            print("=" * 80)
            import_from_directory(
                directory=models_dir,
                base_package='test_lazy'
            )
            print(">>> インポート完了: まだマッパー設定は行われていない")

            print("\n" + "=" * 80)
            print("STEP 2: configure_mappers() を明示的に呼び出す")
            print("=" * 80)

            # この時点で名前解決が行われる
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                configure_mappers()

                if w:
                    print(f"⚠️  警告が発生しました:")
                    for warning in w:
                        print(f"   {warning.category.__name__}: {warning.message}")
                else:
                    print("✅ 警告なし: 名前解決に成功")

            print("\n" + "=" * 80)
            print("STEP 3: データベース操作")
            print("=" * 80)

            # データベースを作成
            engine = create_engine("sqlite:///:memory:", echo=False)
            from repom.models.base_model import BaseModel
            BaseModel.metadata.create_all(engine)

            # モデルを取得
            test_lazy = sys.modules.get('test_lazy.a_parent')
            AParentModel = getattr(test_lazy, 'AParentModel')

            with Session(engine) as session:
                parent = AParentModel(name="Test Parent")
                session.add(parent)
                session.flush()

                print(f"✅ Parent created: {parent.name}")
                print(f"✅ children relationship exists: {hasattr(parent, 'children')}")
                print(f"✅ children value: {parent.children}")

        finally:
            if str(temp_dir) in sys.path:
                sys.path.remove(str(temp_dir))
            modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_lazy')]
            for module in modules_to_remove:
                del sys.modules[module]
            from repom.models.base_model import BaseModel
            BaseModel.metadata.clear()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_actual_failure_scenario(isolated_mapper_registry):
    """
    実際にエラーが発生するシナリオを特定する

    仮説:
    1. TYPE_CHECKING ブロック内のインポートは実行時に実行されない
    2. しかし auto_import_models() が両方のファイルをインポートする
    3. そのため、両方のクラスがグローバル名前空間に登録される
    4. SQLAlchemy は文字列参照を registry から解決できる

    エラーが発生する条件:
    - 一方のモデルファイルが auto_import_models() でインポートされない
    - または、インポートに失敗する

    Note:
    - isolated_mapper_registry フィクスチャにより、テスト終了後に自動クリーンアップ
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="test_failure_"))

    try:
        models_dir = temp_dir / "test_failure"
        models_dir.mkdir(parents=True)

        (models_dir / "__init__.py").write_text("", encoding='utf-8')

        # Parent model
        (models_dir / "parent.py").write_text("""
from typing import TYPE_CHECKING, List
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import String
from repom.models.base_model_auto import BaseModelAuto

if TYPE_CHECKING:
    from .child_not_imported import ChildNotImportedModel

class ParentModel(BaseModelAuto):
    __tablename__ = 'parents'
    name: Mapped[str] = mapped_column(String(50))
    
    # ChildNotImportedModel は存在しないので、名前解決失敗するはず
    children: Mapped[List["ChildNotImportedModel"]] = relationship()
""", encoding='utf-8')

        # child ファイルは作成しない（インポートされない）

        sys.path.insert(0, str(temp_dir))

        try:
            from repom._.discovery import import_from_directory
            from sqlalchemy.orm import configure_mappers

            print("\n" + "=" * 80)
            print("テスト: child ファイルが存在しない場合")
            print("=" * 80)

            import_from_directory(
                directory=models_dir,
                base_package='test_failure'
            )

            print(">>> import_from_directory 完了")

            # マッパー設定時にエラーが発生するはず
            print(">>> configure_mappers() を呼び出し...")

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                try:
                    configure_mappers()
                    print("✅ configure_mappers() 成功（予想外）")
                except Exception as e:
                    print(f"❌ エラー発生（予想通り）: {type(e).__name__}: {e}")

                if w:
                    print(f"⚠️  警告:")
                    for warning in w:
                        print(f"   {warning.message}")

        finally:
            if str(temp_dir) in sys.path:
                sys.path.remove(str(temp_dir))
            modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_failure')]
            for module in modules_to_remove:
                del sys.modules[module]
            from repom.models.base_model import BaseModel
            BaseModel.metadata.clear()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    print("=" * 80)
    print("Test 1: Import order inspection")
    print("=" * 80)
    test_inspect_import_order()

    print("\n" + "=" * 80)
    print("Test 2: SQLAlchemy lazy resolution")
    print("=" * 80)
    test_sqlalchemy_relationship_lazy_resolution()

    print("\n" + "=" * 80)
    print("Test 3: Actual failure scenario")
    print("=" * 80)
    test_actual_failure_scenario()
