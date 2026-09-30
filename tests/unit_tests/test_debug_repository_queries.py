"""debug_repository_queries のモジュールインポートに関するテスト

repom.scripts.debug_repository_queries をインポートしただけで
repom.examples.repositories.sample がインポートされ、SampleModel の
"samples" テーブルが共有の Base.metadata に登録されてしまわないことを
確認します。同一プロセス内では他のテストが既に repom.examples.models を
ロードしているため、サブプロセス（新規インタプリタ）で検証します。
"""

import subprocess
import sys

import pytest

from repom.examples.repositories.sample import SampleRepository
from repom.scripts import debug_repository_queries as query_script

def test_importing_module_does_not_register_samples_table():
    code = (
        "import os\n"
        "os.environ.setdefault('EXEC_ENV', 'test')\n"
        "import repom.scripts.debug_repository_queries  # noqa: F401\n"
        "from repom.models.base_model import Base\n"
        "assert 'samples' not in Base.metadata.tables, sorted(Base.metadata.tables)\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_main_imports_module_class_target(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["debug_repository_queries", "repom.examples.repositories.sample:SampleRepository"])
    monkeypatch.setattr(query_script, "debug_repository_queries", calls.append)

    query_script.main()

    assert calls == [SampleRepository]


def test_main_rejects_target_without_class_separator(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["debug_repository_queries", "repom.examples.repositories.sample"])

    with pytest.raises(SystemExit) as exc_info:
        query_script.main()

    assert exc_info.value.code == 2


def test_main_uses_default_sample_repository(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["debug_repository_queries"])
    monkeypatch.setattr(query_script, "debug_repository_queries", calls.append)

    query_script.main()

    assert calls == [SampleRepository]
