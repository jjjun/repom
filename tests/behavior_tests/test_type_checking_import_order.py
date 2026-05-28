"""
Test for TYPE_CHECKING import order issue with auto_import_models

This test reproduces the issue described in:
mine-py/docs/issues/active/alphabetical_import_order_breaks_sqlalchemy_relationships.md

Issue Summary:
- auto_import_models() imports files alphabetically
- When using TYPE_CHECKING blocks, models imported there are not available at runtime
- SQLAlchemy's relationship string references fail to resolve if the target model
  hasn't been imported yet
"""

import sys
import tempfile
import shutil
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest


def test_type_checking_with_alphabetical_import_order():
    """
    : TYPE_CHECKING + 

    :
    - ani_video_item.py (a   )
    - ani_video_user_status.py (u   )

    :
    - ani_video_item.py 
    - TYPE_CHECKING  AniVideoUserStatusModel 
    - relationship  "AniVideoUserStatusModel" 
    -  AniVideoUserStatusModel 
    - SQLAlchemy 
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers
    # 
    temp_dir = Path(tempfile.mkdtemp(prefix="test_models_"))

    try:
        # 
        models_dir = temp_dir / "test_models"
        models_dir.mkdir(parents=True)

        # __init__.py 
        init_file = models_dir / "__init__.py"
        init_file.write_text("""
# Empty init file - import_from_directory will skip this
""", encoding='utf-8')

        # ani_video_item.py a   
        video_item_file = models_dir / "ani_video_item.py"
        video_item_file.write_text("""
from typing import TYPE_CHECKING, List
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

if TYPE_CHECKING:
    from .ani_video_user_status import AniVideoUserStatusModel

class AniVideoItemModel(BaseModelAuto):
    __tablename__ = 'ani_video_items'
    
    title: Mapped[str] = mapped_column(String(200))
    
    # relationship with string reference
    user_statuses: Mapped[List["AniVideoUserStatusModel"]] = relationship(
        back_populates="ani_video_item",
        cascade="all, delete-orphan"
    )
""", encoding='utf-8')

        # ani_video_user_status.py u   
        user_status_file = models_dir / "ani_video_user_status.py"
        user_status_file.write_text("""
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

if TYPE_CHECKING:
    from .ani_video_item import AniVideoItemModel

class AniVideoUserStatusModel(BaseModelAuto):
    __tablename__ = 'ani_video_user_statuses'
    
    ani_video_item_id: Mapped[int] = mapped_column(ForeignKey('ani_video_items.id'))
    status: Mapped[str] = mapped_column(String(50))
    
    # relationship with string reference
    ani_video_item: Mapped["AniVideoItemModel"] = relationship(
        back_populates="user_statuses"
    )
""", encoding='utf-8')

        # sys.path 
        sys.path.insert(0, str(temp_dir))

        try:
            # import_from_directory 
            from basekit.discovery import import_from_directory

            # 
            # "expression 'AniVideoUserStatusModel' failed to locate a name"
            import_from_directory(
                directory=models_dir,
                base_package='test_models'
            )

            # 
            test_models = sys.modules.get('test_models.ani_video_item')
            assert test_models is not None, "ani_video_item module should be imported"

            # AniVideoItemModel 
            AniVideoItemModel = getattr(test_models, 'AniVideoItemModel', None)
            assert AniVideoItemModel is not None, "AniVideoItemModel should be imported"

            # 
            engine = create_engine("sqlite:///:memory:", echo=False)

            # 
            from repom.models.base_model import BaseModel
            BaseModel.metadata.create_all(engine)

            # 
            with Session(engine) as session:
                # AniVideoItemModel 
                video_item = AniVideoItemModel(title="Test Video")
                session.add(video_item)
                session.flush()

                # user_statuses relationship 
                # 
                assert hasattr(video_item, 'user_statuses'), "user_statuses relationship should exist"
                assert video_item.user_statuses == [], "user_statuses should be empty list"

            print("Test passed: Relationships work despite TYPE_CHECKING blocks")
            print("   (This means SQLAlchemy resolved the string references successfully)")

        except Exception as e:
            # 
            error_msg = str(e)

            # 
            if "failed to locate a name" in error_msg.lower():
                pytest.fail(
                    f"[NG] Name resolution failed as expected:\n{error_msg}\n\n"
                    "This confirms the issue: TYPE_CHECKING blocks + alphabetical import order "
                    "causes SQLAlchemy relationship string references to fail."
                )
            else:
                # raise
                raise

    finally:
        # 
        if str(temp_dir) in sys.path:
            sys.path.remove(str(temp_dir))

        # sys.modules 
        modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_models')]
        for module in modules_to_remove:
            del sys.modules[module]

        # 
        shutil.rmtree(temp_dir, ignore_errors=True)
        # 
        clear_mappers()
        configure_mappers()


def test_type_checking_with_manual_import_order():
    """
    : TYPE_CHECKING 

    TYPE_CHECKING 
    
    """
    # 
    temp_dir = Path(tempfile.mkdtemp(prefix="test_models_fixed_"))

    try:
        # 
        models_dir = temp_dir / "test_models_fixed"
        models_dir.mkdir(parents=True)

        # __init__.py 
        init_file = models_dir / "__init__.py"
        init_file.write_text("""
# Empty init file
""", encoding='utf-8')

        # ani_video_item.py TYPE_CHECKING 
        video_item_file = models_dir / "ani_video_item.py"
        video_item_file.write_text("""
from typing import List
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

# TYPE_CHECKING 
from .ani_video_user_status import AniVideoUserStatusModel

class AniVideoItemModel(BaseModelAuto):
    __tablename__ = 'ani_video_items_fixed'
    
    title: Mapped[str] = mapped_column(String(200))
    
    # relationship with string reference
    user_statuses: Mapped[List["AniVideoUserStatusModel"]] = relationship(
        back_populates="ani_video_item",
        cascade="all, delete-orphan"
    )
""", encoding='utf-8')

        # ani_video_user_status.py 
        user_status_file = models_dir / "ani_video_user_status.py"
        user_status_file.write_text("""
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

# 
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .ani_video_item import AniVideoItemModel

class AniVideoUserStatusModel(BaseModelAuto):
    __tablename__ = 'ani_video_user_statuses_fixed'
    
    ani_video_item_id: Mapped[int] = mapped_column(ForeignKey('ani_video_items_fixed.id'))
    status: Mapped[str] = mapped_column(String(50))
    
    # relationship with string reference
    ani_video_item: Mapped["AniVideoItemModel"] = relationship(
        back_populates="user_statuses"
    )
""", encoding='utf-8')

        # sys.path 
        sys.path.insert(0, str(temp_dir))

        try:
            # import_from_directory 
            from basekit.discovery import import_from_directory

            # 
            import_from_directory(
                directory=models_dir,
                base_package='test_models_fixed'
            )

            # 
            test_models = sys.modules.get('test_models_fixed.ani_video_item')
            assert test_models is not None, "ani_video_item module should be imported"

            # AniVideoItemModel 
            AniVideoItemModel = getattr(test_models, 'AniVideoItemModel', None)
            assert AniVideoItemModel is not None, "AniVideoItemModel should be imported"

            # 
            engine = create_engine("sqlite:///:memory:", echo=False)

            # 
            from repom.models.base_model import BaseModel
            BaseModel.metadata.create_all(engine)

            # 
            with Session(engine) as session:
                # AniVideoItemModel 
                video_item = AniVideoItemModel(title="Test Video Fixed")
                session.add(video_item)
                session.flush()

                # user_statuses relationship 
                assert hasattr(video_item, 'user_statuses'), "user_statuses relationship should exist"
                assert video_item.user_statuses == [], "user_statuses should be empty list"

            print("Test passed: Relationships work correctly when imports are outside TYPE_CHECKING")

        finally:
            # 
            if str(temp_dir) in sys.path:
                sys.path.remove(str(temp_dir))

            # sys.modules 
            modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_models_fixed')]
            for module in modules_to_remove:
                del sys.modules[module]

    finally:
        # 
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    print("=" * 80)
    print("Test 1: TYPE_CHECKING with alphabetical import order (Expected to show issue)")
    print("=" * 80)
    try:
        test_type_checking_with_alphabetical_import_order()
    except Exception as e:
        print(f"Test 1 result: {e}")

    print("\n" + "=" * 80)
    print("Test 2: Manual import order (Expected to work)")
    print("=" * 80)
    test_type_checking_with_manual_import_order()


