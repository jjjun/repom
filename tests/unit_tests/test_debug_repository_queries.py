"""debug_repository_queries のモジュールインポートに関するテスト

repom.scripts.debug_repository_queries をインポートしただけで
repom.examples.repositories.sample がインポートされ、SampleModel の
"samples" テーブルが共有の Base.metadata に登録されてしまわないことを
確認します。同一プロセス内では他のテストが既に repom.examples.models を
ロードしているため、サブプロセス（新規インタプリタ）で検証します。
"""

import subprocess
import sys


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
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
