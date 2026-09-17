"""normalize_text() のテスト

NFKC 正規化と空白除去・小文字化の組み合わせが、半角・全角の入力で
一貫した結果を返すことを確認します。
"""

import pytest

from repom.utility import normalize_text


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
