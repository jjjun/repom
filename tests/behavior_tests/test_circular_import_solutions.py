"""循環参照問題の解決方法を検証するテスト

このテストでは、以下の2つのアプローチを検証します：
1. すべてのモデルを先にインポートしてからマッパー初期化
2. 循環参照を解消する設計パターン
"""
import pytest
from repom.models.base_model import Base


class TestSolution1_DeferredMapperConfiguration:
    """解決策1: すべてのモデルをインポート後にマッパー初期化"""

    def test_deferred_mapper_configuration(self):
        """すべてのモデルをインポートしてから configure_mappers() を呼ぶ

        改良版の import_from_packages() のシミュレーション。

        手順：
        1. すべてのパッケージをインポート（マッパー初期化なし）
        2. すべてのインポート完了後に configure_mappers() を呼ぶ
        3. エラーなく初期化できることを確認
        """
        from repom._.discovery import import_package_directory
        from sqlalchemy.orm import configure_mappers, clear_mappers

        # クリーンアップ
        Base.metadata.clear()
        clear_mappers()

        # モジュールキャッシュをクリア
        import sys
        for key in list(sys.modules.keys()):
            if 'tests.fixtures.circular_import' in key:
                del sys.modules[key]

        try:
            print("\n=== 改良版アプローチ：遅延マッパー初期化 ===")

            # Step 1: すべてのパッケージをインポート
            # （この時点では configure_mappers は呼ばない）
            print("Step 1: Import all packages without configuring mappers")

            packages = [
                'tests.fixtures.circular_import.package_a',
                'tests.fixtures.circular_import.package_b',
            ]

            for package_name in packages:
                print(f"  - Importing {package_name}")
                import_package_directory(
                    package_name=package_name,
                    excluded_dirs=set(),
                    allowed_prefixes={'tests.fixtures.', 'repom.'}
                )

            print("✅ All packages imported")

            # Step 2: すべてのインポートが完了してから、マッパーを初期化
            print("\nStep 2: Configure all mappers at once")
            configure_mappers()
            print("✅ Mappers configured successfully")

            # Step 3: モデルが使えることを確認
            print("\nStep 3: Verify models are usable")
            from tests.fixtures.circular_import.package_a.model_a import ModelA
            from tests.fixtures.circular_import.package_b.model_b import ModelB
            from sqlalchemy.orm import class_mapper

            mapper_a = class_mapper(ModelA)
            mapper_b = class_mapper(ModelB)

            print(f"✅ ModelA mapper: {mapper_a}")
            print(f"✅ ModelB mapper: {mapper_b}")

            assert mapper_a is not None
            assert mapper_b is not None

            print("\n🎉 解決策1は有効：すべてインポート後のマッパー初期化で成功！")

        finally:
            # クリーンアップ
            Base.metadata.clear()
            clear_mappers()

            # モジュールキャッシュをクリア
            for key in list(sys.modules.keys()):
                if 'tests.fixtures.circular_import' in key:
                    del sys.modules[key]

    def test_improved_auto_import_models_from_list(self):
        """改良版 import_from_packages の実装例

        この関数は、以下の改良を加えています：
        1. すべてのパッケージをインポート
        2. 最後に configure_mappers() を1回だけ呼ぶ
        3. エラーハンドリング
        """
        from sqlalchemy.orm import configure_mappers, clear_mappers

        # クリーンアップ
        Base.metadata.clear()
        clear_mappers()

        # モジュールキャッシュをクリア
        import sys
        for key in list(sys.modules.keys()):
            if 'tests.fixtures.circular_import' in key:
                del sys.modules[key]

        try:
            # 改良版の実装
            def auto_import_models_from_list_v2(
                package_names,
                excluded_dirs=None,
                allowed_prefixes=None,
                fail_on_error=False
            ):
                """改良版：すべてインポート後にマッパー初期化"""
                from repom._.discovery import import_package_directory

                # Phase 1: すべてのパッケージをインポート
                for package_name in package_names:
                    failures = import_package_directory(
                        package_name=package_name,
                        excluded_dirs=excluded_dirs,
                        allowed_prefixes=allowed_prefixes,
                        fail_on_error=fail_on_error
                    )
                    if failures and not fail_on_error:
                        for failure in failures:
                            print(f"Warning: Failed to import {failure.target}: {failure.message}")

                # Phase 2: すべてのインポート完了後にマッパー初期化
                try:
                    configure_mappers()
                except Exception as e:
                    if fail_on_error:
                        raise
                    else:
                        print(f"Warning: Failed to configure mappers: {e}")

            # テスト実行
            print("\n=== 改良版関数のテスト ===")
            auto_import_models_from_list_v2(
                package_names=[
                    'tests.fixtures.circular_import.package_a',
                    'tests.fixtures.circular_import.package_b',
                ],
                excluded_dirs=set(),
                allowed_prefixes={'tests.fixtures.', 'repom.'},
                fail_on_error=False
            )

            # 検証
            from tests.fixtures.circular_import.package_a.model_a import ModelA
            from tests.fixtures.circular_import.package_b.model_b import ModelB
            from sqlalchemy.orm import class_mapper

            mapper_a = class_mapper(ModelA)
            mapper_b = class_mapper(ModelB)

            assert mapper_a is not None
            assert mapper_b is not None

            print("✅ 改良版関数は正常に動作")
            print(f"   ModelA: {mapper_a}")
            print(f"   ModelB: {mapper_b}")

        finally:
            # クリーンアップ
            Base.metadata.clear()
            clear_mappers()

            # モジュールキャッシュをクリア
            for key in list(sys.modules.keys()):
                if 'tests.fixtures.circular_import' in key:
                    del sys.modules[key]


class TestSolution2_DesignPatterns:
    """解決策2: 循環参照を解消する設計パターン"""

    def test_pattern1_foreign_key_explicit_declaration(self):
        """パターン1: relationship() で foreign_keys を明示的に指定

        SQLAlchemy に対して、どのカラムが外部キーなのかを明示的に伝えることで、
        文字列参照の解決を支援する。

        ただし、このパターンだけでは循環参照問題は解決しない。
        """
        print("\n=== パターン1: foreign_keys 明示的指定 ===")
        print("説明：relationship() で foreign_keys 引数を使う")
        print("効果：部分的な改善のみ（根本解決にはならない）")
        print("実装例：")
        print("""
        class ModelA(BaseModelAuto):
            children: Mapped[List["ModelB"]] = relationship(
                "ModelB",
                back_populates="parent",
                foreign_keys="ModelB.parent_id",  # 明示的指定
                cascade="all, delete-orphan"
            )
        """)

    def test_pattern2_use_string_references_with_registry(self):
        """パターン2: registry を使った文字列参照の改善

        SQLAlchemy 2.0 では、モデルは自動的に registry に登録される。
        文字列参照を使う際は、完全修飾名（モジュールパス含む）ではなく
        クラス名のみを使用する。

        現在のコードは既にこのパターンを使用している。
        """
        print("\n=== パターン2: registry を使った文字列参照 ===")
        print("説明：クラス名のみで参照（モジュールパス不要）")
        print("効果：SQLAlchemy の標準的な方法")
        print("実装例：")
        print("""
        # ✅ 良い例：クラス名のみ
        children: Mapped[List["ModelB"]] = relationship(...)
        
        # ❌ 避けるべき：完全修飾名
        children: Mapped[List["package_b.model_b.ModelB"]] = relationship(...)
        """)
        print("現在のコードは既にこのパターンを使用しています。")

    def test_pattern3_relationship_after_class_definition(self):
        """パターン3: クラス定義後に relationship を追加

        最も確実な方法：
        1. すべてのモデルクラスを定義
        2. その後で relationship を追加

        ただし、コードが分散するため保守性が下がる。
        """
        from sqlalchemy import String, Integer, ForeignKey
        from sqlalchemy.orm import relationship, mapped_column, Mapped, clear_mappers
        from typing import List
        from repom import BaseModelAuto

        # クリーンアップ
        Base.metadata.clear()
        clear_mappers()

        try:
            print("\n=== パターン3: relationship を後から追加 ===")

            # Step 1: relationship なしでモデルを定義
            print("Step 1: Define models without relationships")

            class ModelC(BaseModelAuto, use_created_at=True):
                __tablename__ = 'test_model_c'
                name: Mapped[str] = mapped_column(String(255), nullable=False)

            class ModelD(BaseModelAuto, use_created_at=True):
                __tablename__ = 'test_model_d'
                parent_id: Mapped[int] = mapped_column(
                    Integer,
                    ForeignKey('test_model_c.id', ondelete='CASCADE'),
                    nullable=False,
                    index=True
                )

            print("✅ Models defined without relationships")

            # Step 2: すべてのクラスが定義された後で relationship を追加
            print("\nStep 2: Add relationships after all classes are defined")

            ModelC.children = relationship(
                ModelD,
                back_populates="parent",
                cascade="all, delete-orphan",
                lazy="selectin"
            )

            ModelD.parent = relationship(
                ModelC,
                back_populates="children"
            )

            print("✅ Relationships added")

            # Step 3: マッパーを初期化
            from sqlalchemy.orm import configure_mappers, class_mapper
            configure_mappers()

            mapper_c = class_mapper(ModelC)
            mapper_d = class_mapper(ModelD)

            print(f"\n✅ ModelC mapper: {mapper_c}")
            print(f"✅ ModelD mapper: {mapper_d}")

            assert mapper_c is not None
            assert mapper_d is not None

            print("\n🎉 パターン3は有効だが、コードが分散するため推奨しない")

        finally:
            # クリーンアップ
            Base.metadata.clear()
            clear_mappers()

    def test_pattern4_avoid_circular_references_in_design(self):
        """パターン4: 設計レベルで循環参照を避ける

        最も根本的な解決策：
        - 双方向の relationship を避ける
        - 必要に応じて一方向のみにする
        - または中間テーブルを使う
        """
        from sqlalchemy import String, Integer, ForeignKey
        from sqlalchemy.orm import relationship, mapped_column, Mapped, clear_mappers
        from repom import BaseModelAuto

        # クリーンアップ
        Base.metadata.clear()
        clear_mappers()

        try:
            print("\n=== パターン4: 設計レベルで循環参照を避ける ===")

            # アプローチA: 一方向の relationship のみ
            print("\nアプローチA: 子→親の一方向のみ")

            class ParentModel(BaseModelAuto, use_created_at=True):
                __tablename__ = 'test_parent'
                name: Mapped[str] = mapped_column(String(255), nullable=False)
                # relationship なし（親から子へのアクセスは不要）

            class ChildModel(BaseModelAuto, use_created_at=True):
                __tablename__ = 'test_child'
                parent_id: Mapped[int] = mapped_column(
                    Integer,
                    ForeignKey('test_parent.id', ondelete='CASCADE'),
                    nullable=False,
                    index=True
                )
                # 子から親へのみ relationship を定義
                parent: Mapped[ParentModel] = relationship(ParentModel)

            from sqlalchemy.orm import configure_mappers, class_mapper
            configure_mappers()

            mapper_parent = class_mapper(ParentModel)
            mapper_child = class_mapper(ChildModel)

            print(f"✅ ParentModel mapper: {mapper_parent}")
            print(f"✅ ChildModel mapper: {mapper_child}")

            print("\nメリット：")
            print("  - 循環参照がないので初期化エラーなし")
            print("  - シンプルで理解しやすい")
            print("\nデメリット：")
            print("  - 親から子へのアクセスには明示的なクエリが必要")
            print("  - ORM の利便性が減少")

            print("\n推奨シナリオ：")
            print("  - 親→子のアクセスが不要な場合")
            print("  - パフォーマンスが重要な場合")

        finally:
            # クリーンアップ
            Base.metadata.clear()
            clear_mappers()


class TestSolution_Comparison:
    """各解決策の比較と推奨事項"""

    def test_solution_comparison_summary(self):
        """各解決策の比較表"""
        print("\n" + "="*80)
        print("循環参照問題の解決策比較")
        print("="*80)

        print("\n【解決策1】すべてのモデルをインポート後にマッパー初期化")
        print("  実装難易度: ★☆☆☆☆ (簡単)")
        print("  効果:       ★★★★★ (完全に解決)")
        print("  保守性:     ★★★★★ (既存コードの変更不要)")
        print("  推奨度:     ★★★★★")
        print("  ")
        print("  メリット:")
        print("    ✓ 既存のモデル定義を変更する必要がない")
        print("    ✓ import_from_packages() の改良だけで対応可能")
        print("    ✓ すべての循環参照パターンに対応")
        print("  ")
        print("  デメリット:")
        print("    ✗ マッパー初期化のタイミングを制御する必要がある")
        print("  ")
        print("  実装方法:")
        print("    1. import_from_packages() を改良")
        print("    2. すべてのパッケージをインポート後、configure_mappers() を呼ぶ")

        print("\n" + "-"*80)

        print("\n【解決策2-A】relationship を後から追加")
        print("  実装難易度: ★★★☆☆ (中)")
        print("  効果:       ★★★★☆ (有効)")
        print("  保守性:     ★★☆☆☆ (コードが分散)")
        print("  推奨度:     ★★☆☆☆")
        print("  ")
        print("  メリット:")
        print("    ✓ 確実に循環参照を回避")
        print("  ")
        print("  デメリット:")
        print("    ✗ コードが分散して保守しにくい")
        print("    ✗ すべてのモデルで同じパターンを適用する必要がある")

        print("\n" + "-"*80)

        print("\n【解決策2-B】一方向の relationship のみ")
        print("  実装難易度: ★☆☆☆☆ (簡単)")
        print("  効果:       ★★★★★ (完全に回避)")
        print("  保守性:     ★★★★☆ (シンプル)")
        print("  推奨度:     ★★★★☆ (ケースによる)")
        print("  ")
        print("  メリット:")
        print("    ✓ 循環参照が発生しない")
        print("    ✓ シンプルで理解しやすい")
        print("  ")
        print("  デメリット:")
        print("    ✗ 双方向のナビゲーションが必要な場合には不向き")
        print("    ✗ ORM の利便性が減少")
        print("  ")
        print("  推奨シナリオ:")
        print("    - 親→子のアクセスが不要")
        print("    - クエリで十分な場合")

        print("\n" + "="*80)
        print("💡 総合推奨：解決策1（すべてインポート後のマッパー初期化）")
        print("="*80)
        print("理由：")
        print("  1. 既存コードの変更が最小限")
        print("  2. すべての循環参照パターンに対応")
        print("  3. ORM の利便性を保持")
        print("  4. 実装が比較的簡単")
        print("="*80 + "\n")
