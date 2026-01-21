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


def test_type_checking_with_alphabetical_import_order(isolated_mapper_registry):
    """
    再現テスト: TYPE_CHECKING + アルファベット順インポートで名前解決エラー

    ファイル構成:
    - ani_video_item.py (a で始まる → 先にインポート)
    - ani_video_user_status.py (u で始まる → 後でインポート)

    問題:
    - ani_video_item.py が先にインポートされる
    - TYPE_CHECKING ブロック内で AniVideoUserStatusModel をインポート
    - relationship で "AniVideoUserStatusModel" を参照
    - しかし実行時には AniVideoUserStatusModel がまだインポートされていない
    - SQLAlchemy の名前解決が失敗

    Note:
    - isolated_mapper_registry フィクスチャにより、テスト終了後に自動クリーンアップ
    """
    # 一時ディレクトリ作成
    temp_dir = Path(tempfile.mkdtemp(prefix="test_models_"))

    try:
        # テストモデルディレクトリを作成
        models_dir = temp_dir / "test_models"
        models_dir.mkdir(parents=True)

        # __init__.py を作成
        init_file = models_dir / "__init__.py"
        init_file.write_text("""
# Empty init file - auto_import_models will skip this
""", encoding='utf-8')

        # ani_video_item.py を作成（a で始まる → 先にインポート）
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

        # ani_video_user_status.py を作成（u で始まる → 後でインポート）
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

        # sys.path にディレクトリを追加
        sys.path.insert(0, str(temp_dir))

        try:
            # auto_import_models を実行
            from repom.utility import auto_import_models

            # この時点で警告が発生するはず
            # "expression 'AniVideoUserStatusModel' failed to locate a name"
            auto_import_models(
                models_dir=models_dir,
                base_package='test_models'
            )

            # モデルがインポートされているか確認
            test_models = sys.modules.get('test_models.ani_video_item')
            assert test_models is not None, "ani_video_item module should be imported"

            # AniVideoItemModel が存在するか確認
            AniVideoItemModel = getattr(test_models, 'AniVideoItemModel', None)
            assert AniVideoItemModel is not None, "AniVideoItemModel should be imported"

            # データベースを作成してマッパーが正しく動作するか確認
            engine = create_engine("sqlite:///:memory:", echo=False)

            # メタデータから全テーブルを作成
            from repom.models.base_model import BaseModel
            BaseModel.metadata.create_all(engine)

            # セッションを作成してオブジェクトを作成できるか確認
            with Session(engine) as session:
                # AniVideoItemModel を作成
                video_item = AniVideoItemModel(title="Test Video")
                session.add(video_item)
                session.flush()

                # user_statuses relationship にアクセスできるか
                # もし名前解決が失敗していれば、ここでエラーになる
                assert hasattr(video_item, 'user_statuses'), "user_statuses relationship should exist"
                assert video_item.user_statuses == [], "user_statuses should be empty list"

            print("✅ Test passed: Relationships work despite TYPE_CHECKING blocks")
            print("   (This means SQLAlchemy resolved the string references successfully)")

        except Exception as e:
            # エラーメッセージを確認
            error_msg = str(e)

            # 予想されるエラーメッセージ
            if "failed to locate a name" in error_msg.lower():
                pytest.fail(
                    f"❌ Name resolution failed as expected:\n{error_msg}\n\n"
                    "This confirms the issue: TYPE_CHECKING blocks + alphabetical import order "
                    "causes SQLAlchemy relationship string references to fail."
                )
            else:
                # 別のエラーの場合は再度raise
                raise

    finally:
        # クリーンアップ
        if str(temp_dir) in sys.path:
            sys.path.remove(str(temp_dir))

        # sys.modules からテストモジュールを削除
        modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_models')]
        for module in modules_to_remove:
            del sys.modules[module]

        # 一時ディレクトリを削除
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Note: マッパーとメタデータのクリーンアップは isolated_mapper_registry が自動的に行う


def test_type_checking_with_manual_import_order(isolated_mapper_registry):
    """
    解決策のテスト: TYPE_CHECKING を外して実際にインポート

    このテストでは、TYPE_CHECKING を使わずに直接インポートすることで
    問題が解決することを確認する

    Note:
    - isolated_mapper_registry フィクスチャにより、テスト終了後に自動クリーンアップ
    """
    # 一時ディレクトリ作成
    temp_dir = Path(tempfile.mkdtemp(prefix="test_models_fixed_"))

    try:
        # テストモデルディレクトリを作成
        models_dir = temp_dir / "test_models_fixed"
        models_dir.mkdir(parents=True)

        # __init__.py を作成
        init_file = models_dir / "__init__.py"
        init_file.write_text("""
# Empty init file
""", encoding='utf-8')

        # ani_video_item.py を作成（TYPE_CHECKING を使わない）
        video_item_file = models_dir / "ani_video_item.py"
        video_item_file.write_text("""
from typing import List
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

# TYPE_CHECKING の外でインポート（実行時にも利用可能）
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

        # ani_video_user_status.py を作成
        user_status_file = models_dir / "ani_video_user_status.py"
        user_status_file.write_text("""
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from repom.models.base_model_auto import BaseModelAuto

# 前方参照を使うので循環インポートは発生しない
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

        # sys.path にディレクトリを追加
        sys.path.insert(0, str(temp_dir))

        try:
            # auto_import_models を実行
            from repom.utility import auto_import_models

            # この時点では警告が発生しないはず
            auto_import_models(
                models_dir=models_dir,
                base_package='test_models_fixed'
            )

            # モデルがインポートされているか確認
            test_models = sys.modules.get('test_models_fixed.ani_video_item')
            assert test_models is not None, "ani_video_item module should be imported"

            # AniVideoItemModel が存在するか確認
            AniVideoItemModel = getattr(test_models, 'AniVideoItemModel', None)
            assert AniVideoItemModel is not None, "AniVideoItemModel should be imported"

            # データベースを作成してマッパーが正しく動作するか確認
            engine = create_engine("sqlite:///:memory:", echo=False)

            # メタデータから全テーブルを作成
            from repom.models.base_model import BaseModel
            BaseModel.metadata.create_all(engine)

            # セッションを作成してオブジェクトを作成できるか確認
            with Session(engine) as session:
                # AniVideoItemModel を作成
                video_item = AniVideoItemModel(title="Test Video Fixed")
                session.add(video_item)
                session.flush()

                # user_statuses relationship にアクセスできるか
                assert hasattr(video_item, 'user_statuses'), "user_statuses relationship should exist"
                assert video_item.user_statuses == [], "user_statuses should be empty list"

            print("✅ Test passed: Relationships work correctly when imports are outside TYPE_CHECKING")

        finally:
            # クリーンアップ
            if str(temp_dir) in sys.path:
                sys.path.remove(str(temp_dir))

            # sys.modules からテストモジュールを削除
            modules_to_remove = [key for key in sys.modules.keys() if key.startswith('test_models_fixed')]
            for module in modules_to_remove:
                del sys.modules[module]

    finally:
        # 一時ディレクトリを削除
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Note: マッパーとメタデータのクリーンアップは isolated_mapper_registry が自動的に行う


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
