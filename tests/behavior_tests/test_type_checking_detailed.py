"""
: TYPE_CHECKING  auto_import_models 

:
1. auto_import_models 
2. TYPE_CHECKING 
3. SQLAlchemy 
4. 
"""

import sys
import tempfile
import shutil
import warnings
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_inspect_import_order():
    """
    import_from_directory 
    """
    # 
    temp_dir = Path(tempfile.mkdtemp(prefix="test_order_"))

    try:
        # 
        models_dir = temp_dir / "test_order"
        models_dir.mkdir(parents=True)

        # __init__.py
        (models_dir / "__init__.py").write_text("", encoding='utf-8')

        # 
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

        # sys.path 
        sys.path.insert(0, str(temp_dir))

        try:
            from basekit.discovery import import_from_directory

            print("\n=== Testing import order ===")
            import_from_directory(
                directory=models_dir,
                base_package='test_order'
            )
            print("=== Import complete ===\n")

            # : a_model, b_model, m_model, z_model ()

        finally:
            # 
            if str(temp_dir) in sys.path:
                sys.path.remove(str(temp_dir))
            modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_order')]
            for module in modules_to_remove:
                del sys.modules[module]
            from repom.models.base_model import BaseModel
            BaseModel.metadata.clear()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sqlalchemy_relationship_lazy_resolution():
    """
    SQLAlchemy  relationship 

    :
    - relationship() 
    - mapper configuration
    - :
      1. 
      2. metadata.create_all() 
      3.  configure_mappers() 
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
    temp_dir = Path(tempfile.mkdtemp(prefix="test_lazy_"))

    try:
        models_dir = temp_dir / "test_lazy"
        models_dir.mkdir(parents=True)

        (models_dir / "__init__.py").write_text("", encoding='utf-8')

        # Parent model ()
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
    
    #  ZChildModel 
    children: Mapped[List["ZChildModel"]] = relationship(
        back_populates="parent"
    )

print(">>> a_parent.py: AParentModel defined successfully")
""", encoding='utf-8')

        # Child model ()
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
            from basekit.discovery import import_from_directory
            from sqlalchemy.orm import configure_mappers

            print("\n" + "=" * 80)
            print("STEP 1: import_from_directory ()")
            print("=" * 80)
            import_from_directory(
                directory=models_dir,
                base_package='test_lazy'
            )
            print(">>> : ")

            print("\n" + "=" * 80)
            print("STEP 2: configure_mappers() ")
            print("=" * 80)

            # 
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                configure_mappers()

                if w:
                    print("[WARN]  :")
                    for warning in w:
                        print(f"   {warning.category.__name__}: {warning.message}")
                else:
                    print(": ")

            print("\n" + "=" * 80)
            print("STEP 3: ")
            print("=" * 80)

            # 
            engine = create_engine("sqlite:///:memory:", echo=False)
            from repom.models.base_model import BaseModel
            BaseModel.metadata.create_all(engine)

            # 
            test_lazy = sys.modules.get('test_lazy.a_parent')
            AParentModel = getattr(test_lazy, 'AParentModel')

            with Session(engine) as session:
                parent = AParentModel(name="Test Parent")
                session.add(parent)
                session.flush()

                print(f"Parent created: {parent.name}")
                print(f"children relationship exists: {hasattr(parent, 'children')}")
                print(f"children value: {parent.children}")

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
        # 
        clear_mappers()
        configure_mappers()


def test_actual_failure_scenario():
    """
    

    :
    1. TYPE_CHECKING 
    2.  auto_import_models() 
    3. 
    4. SQLAlchemy  registry 

    :
    -  auto_import_models() 
    - 
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
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
    
    # ChildNotImportedModel 
    children: Mapped[List["ChildNotImportedModel"]] = relationship()
""", encoding='utf-8')

        # child 

        sys.path.insert(0, str(temp_dir))

        try:
            from basekit.discovery import import_from_directory
            from sqlalchemy.orm import configure_mappers

            print("\n" + "=" * 80)
            print(": child ")
            print("=" * 80)

            import_from_directory(
                directory=models_dir,
                base_package='test_failure'
            )

            print(">>> import_from_directory ")

            # 
            print(">>> configure_mappers() ...")

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                try:
                    configure_mappers()
                    print("configure_mappers() ")
                except Exception as e:
                    print(f"[NG] : {type(e).__name__}: {e}")

                if w:
                    print("[WARN]  :")
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
        # 
        clear_mappers()
        configure_mappers()


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


