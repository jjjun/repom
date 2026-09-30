"""normalize_text() のテスト

NFKC 正規化と空白除去・小文字化の組み合わせが、半角・全角の入力で
一貫した結果を返すことを確認します。
"""

import subprocess
import sys

import pytest

from repom.utility import get_plural_tablename, normalize_text


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Hello World", "helloworld"),
        ("ABC", "abc"),
        ("ＡＢＣ", "abc"),
        ("Ａ　Ｂ　Ｃ", "abc"),
        ("", ""),
    ],
)
def test_normalize_text(value, expected):
    assert normalize_text(value) == expected


def test_get_plural_tablename_pluralizes_file_name():
    assert get_plural_tablename("person.py") == "people"


def test_importing_utility_does_not_import_inflect():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import repom.utility; assert 'inflect' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
