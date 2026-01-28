"""循環参照問題の再現テスト

Issue #020: 循環参照警告の解決（マッパー遅延初期化）
https://github.com/repom/issues/020

複数パッケージから循環参照を持つモデルをインポートする際に、
SQLAlchemy のマッパー初期化でエラーが発生する問題を再現・検証する。

関連：
- mine-py/docs/issues/active/circular_import_mapper_initialization_issue.md
- tests/behavior_tests/test_circular_import_solutions.py（詳細な検証）
"""
import pytest
from repom.models.base_model import Base
from sqlalchemy.orm import clear_mappers


@pytest.fixture
def clean_circular_import_env():
    """循環参照テスト用の環境をクリーンアップ

    各テスト前後で以下を実行：
    - Base.metadata のクリア
    - SQLAlchemy マッパーのクリア
    - モジュールキャッシュのクリア（tests.fixtures.circular_import）

    これにより、テストの独立性を保証し、循環参照エラーを正確に再現できる。
    """
    # 前処理
    Base.metadata.clear()
    clear_mappers()

    import sys
    for key in list(sys.modules.keys()):
        if 'tests.fixtures.circular_import' in key:
            del sys.modules[key]

    yield  # テスト実行

    # 後処理
    Base.metadata.clear()
    clear_mappers()

    for key in list(sys.modules.keys()):
        if 'tests.fixtures.circular_import' in key:
            del sys.modules[key]


class TestCircularImportIssue:
    """Issue #020: 循環参照問題の再現テスト

    検証内容：
    1. 問題の再現：早期マッパー初期化で循環参照エラーが発生
    2. 解決策の検証：遅延マッパー初期化で正常動作

    背景：
    mine-py で発生している「警告」は、auto_import_models_from_list の
    try-except でキャッチされた例外が print で表示されているもの。
    本質的な問題は、マッパー初期化時に参照先のモデルクラスが
    まだ定義されていない（クラスレジストリに未登録）こと。
    """

    def test_reproduce_circular_import_error(self, clean_circular_import_env):
        """循環参照エラーの再現

        条件：package_a のみをインポート後、configure_mappers() を呼ぶ
        期待：ModelB が見つからないエラーが発生
        目的：Issue #020 の問題を再現し、実装前のベースラインを確立

        エラー詳細：
        - ModelA は ModelB を参照している
        - ModelB はまだインポートされていない
        - マッパー初期化時に 'ModelB' という名前が解決できない
        """
        from repom.utility import auto_import_models_by_package
        from sqlalchemy.orm import configure_mappers

        # package_a のみをインポート
        auto_import_models_by_package(
            package_name='tests.fixtures.circular_import.package_a',
            excluded_dirs=set(),
            allowed_prefixes={'tests.fixtures.', 'repom.'}
        )

        # マッパーを強制的に初期化 → エラー発生
        with pytest.raises(Exception) as exc_info:
            configure_mappers()

        # エラーメッセージの検証
        error_message = str(exc_info.value)
        assert "failed to locate a name" in error_message.lower(), (
            f"Expected 'failed to locate a name' in error: {error_message}"
        )
        assert "'ModelB'" in error_message, (
            f"Expected 'ModelB' in error: {error_message}"
        )

    def test_verify_deferred_mapper_solution(self, clean_circular_import_env):
        """遅延マッパー初期化による解決策の検証

        条件：すべてのパッケージをインポート後、configure_mappers() を呼ばない
        期待：マッパーが遅延初期化され、モデルが正常に使用可能
        目的：Issue #020 の解決策（マッパー遅延初期化）が有効であることを検証

        重要な知見：
        - configure_mappers() を明示的に呼ばなければ、エラーは発生しない
        - マッパーは最初のアクセス時に自動的に初期化される
        - その時点ですべてのモデルがインポート済みなら問題なし

        これが解決策1の基礎となる動作である。
        """
        from repom.utility import auto_import_models_by_package
        from sqlalchemy.orm import class_mapper

        # すべてのパッケージをインポート
        auto_import_models_by_package(
            package_name='tests.fixtures.circular_import.package_a',
            excluded_dirs=set(),
            allowed_prefixes={'tests.fixtures.', 'repom.'}
        )

        auto_import_models_by_package(
            package_name='tests.fixtures.circular_import.package_b',
            excluded_dirs=set(),
            allowed_prefixes={'tests.fixtures.', 'repom.'}
        )

        # configure_mappers() は呼ばない（遅延初期化に任せる）

        # モデルクラスを取得
        from tests.fixtures.circular_import.package_a.model_a import ModelA
        from tests.fixtures.circular_import.package_b.model_b import ModelB

        # リレーションシップの確認
        assert hasattr(ModelA, 'children'), "ModelA should have 'children' relationship"
        assert hasattr(ModelB, 'parent'), "ModelB should have 'parent' relationship"

        # マッパーが遅延初期化されることを確認
        mapper_a = class_mapper(ModelA)
        mapper_b = class_mapper(ModelB)

        assert mapper_a is not None, "ModelA mapper should be initialized"
        assert mapper_b is not None, "ModelB mapper should be initialized"

        # テーブルが正しく登録されていることを確認
        tables = list(Base.metadata.tables.keys())
        assert 'test_model_a' in tables, "test_model_a should be registered"
        assert 'test_model_b' in tables, "test_model_b should be registered"
