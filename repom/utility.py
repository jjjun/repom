import os
import inflect
import unicodedata

"""
inflect
英語の単語の複数形、単数形、序数、冠詞などを生成するためのPythonライブラリです。
このライブラリを使用すると、英語の文法規則に基づいて単語の形態を変化させることができます。
主な機能
複数形の生成: 単語の複数形を生成します。
単数形の生成: 単語の単数形を生成します。
序数の生成: 数字を序数(1st, 2nd, 3rd など)に変換します。
冠詞の追加: 単語に適切な冠詞(a, an, the)を追加します。
"""


def get_plural_tablename(file_path: str) -> str:
    """
    ファイル名から拡張子を除去し、複数形に変換してテーブル名を取得する関数。

    Args:
        file_path (str): ファイルのパス

    Returns:
        str: 複数形に変換されたテーブル名
    """
    # ファイル名を取得し、拡張子を除去
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # inflect エンジンを初期化
    p = inflect.engine()

    # ファイル名を複数形に変換
    table_name = p.plural(file_name)

    return table_name


def normalize_text(s: str) -> str:
    """
    テキストの正規化（全角・半角・空白・小文字化）
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "").replace("　", "")
    return s.lower()
