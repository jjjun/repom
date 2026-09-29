"""Behavior coverage for circular SQLAlchemy mapper initialization.

Issue history is stored in issuekit; this file is the executable regression
specification.
"""
from pathlib import Path
import subprocess
import sys


def _run_isolated_python(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )


class TestCircularImportIssue:
    """Issue #020: 循環参照問題の再現テスト

    検証内容：
    1. 問題の再現：早期マッパー初期化で循環参照エラーが発生
    2. 解決策の検証：遅延マッパー初期化で正常動作

    背景：
    mine-py で発生している「警告」は、import_from_packages の
    fail_on_error=False でキャッチされた例外が処理されたもの。
    本質的な問題は、マッパー初期化時に参照先のモデルクラスが
    まだ定義されていない（クラスレジストリに未登録）こと。
    """

    def test_reproduce_circular_import_error(self):
        """循環参照エラーの再現

        条件：package_a のみをインポート後、configure_mappers() を呼ぶ
        期待：ModelB が見つからないエラーが発生
        目的：Issue #020 の問題を再現し、実装前のベースラインを確立

        エラー詳細：
        - ModelA は ModelB を参照している
        - ModelB はまだインポートされていない
        - マッパー初期化時に 'ModelB' という名前が解決できない
        """
        result = _run_isolated_python(
            """
from basekit.discovery import import_package_directory
from sqlalchemy.orm import configure_mappers

import_package_directory(
    package_name="tests.fixtures.circular_import.package_a",
    excluded_dirs=set(),
    allowed_prefixes={"tests.fixtures.", "tests.behavior_tests.", "repom."},
)

try:
    configure_mappers()
except Exception as exc:
    error_message = str(exc)
    assert "failed to locate a name" in error_message.lower(), error_message
    assert "'ModelB'" in error_message, error_message
else:
    raise AssertionError("configure_mappers() should not resolve ModelB")
"""
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_verify_deferred_mapper_solution(self):
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
        result = _run_isolated_python(
            """
from basekit.discovery import import_package_directory
from sqlalchemy.orm import class_mapper

for package_name in (
    "tests.fixtures.circular_import.package_a",
    "tests.fixtures.circular_import.package_b",
):
    import_package_directory(
        package_name=package_name,
        excluded_dirs=set(),
        allowed_prefixes={"tests.fixtures.", "tests.behavior_tests.", "repom."},
    )

from tests.fixtures.circular_import.package_a.model_a import ModelA
from tests.fixtures.circular_import.package_b.model_b import ModelB
from repom.database import Base

assert hasattr(ModelA, "children")
assert hasattr(ModelB, "parent")
assert class_mapper(ModelA) is not None
assert class_mapper(ModelB) is not None
assert "test_model_a" in Base.metadata.tables
assert "test_model_b" in Base.metadata.tables
"""
        )
        assert result.returncode == 0, result.stdout + result.stderr
