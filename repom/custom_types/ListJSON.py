from sqlalchemy.types import TypeDecorator, JSON
from sqlalchemy import func, literal, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
import json


class ListJSON(TypeDecorator):
    """
    List型をJSON形式で保存するためのカスタム型
    次の仕様に沿う
    - 何も代入されていなければ空の配列を返す事を保証
    - List以外を入れたらエラーが出る事を保証
    - 取り出したときに List型であることを保証
    """
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # impl (JSON) が Python オブジェクトを自動でシリアライズするため、ここで
        # json.dumps() すると二重エンコードになり、json_each() など SQL 側で
        # 配列を直接扱う関数が要素を正しく分解できなくなる。ネイティブな値を
        # そのまま返し、シリアライズは impl に任せる。
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Expected a list, but got a different type")
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        if isinstance(value, list):
            result = value
        else:
            result = json.loads(value)
        if not isinstance(result, list):
            raise ValueError("Expected a list, but got a different type")
        return result


class _ListjsonEachValue(GenericFunction):
    """
    ListJSON 列 (JSON 配列) を要素比較用に展開するための関数ラッパー。
    PostgreSQL の json_each()/json_each_text() は JSON オブジェクト専用で
    配列には使えない (cannot deconstruct an array as an object)。配列の要素展開
    には json_array_elements_text() を使う必要があり、これは value を text 型で
    返すため文字列との等価比較もできる。SQLite の json_each() は配列にも
    使え、動的型付けのため文字列比較もそのまま成立するので、SQLite 側は
    従来どおり json_each() を使う。コンパイル時にダイアレクトごとへ振り分ける。
    """
    name = "listjson_each_value"
    inherit_cache = True


@compiles(_ListjsonEachValue)
def _compile_listjson_each_value(element, compiler, **kw):
    return compiler.process(func.json_each(*element.clauses), **kw)


@compiles(_ListjsonEachValue, "postgresql")
def _compile_listjson_each_value_postgresql(element, compiler, **kw):
    return compiler.process(func.json_array_elements_text(*element.clauses), **kw)


class _ListjsonArrayLength(GenericFunction):
    """
    ListJSON 列の要素数を取得するための関数ラッパー。
    func.json_array_length(...) は SQLAlchemy のグローバル関数レジストリを
    名前で解決するため、プロセス内のどこかで sqlalchemy_utils.expressions が
    import されると同モジュールが登録した inherit_cache 未設定の
    json_array_length が優先されてしまい、SQL コンパイルキャッシュが無効化
    されて SAWarning が発生する。レジストリ名に依存しない専用クラスを定義する
    ことでこれを避ける。json_array_length(...) は PostgreSQL / SQLite で構文が
    同じため、_ListjsonEachValue と異なり @compiles はダイアレクト共通の 1 つ
    で足りる。
    """
    name = "listjson_array_length"
    inherit_cache = True


@compiles(_ListjsonArrayLength)
def _compile_listjson_array_length(element, compiler, **kw):
    return compiler.process(func.json_array_length(*element.clauses), **kw)


def listjson_filter(model_column, values):
    """
    Generate SQLAlchemy filter conditions for ListJSON columns.
    - If values == [], filter for empty lists.
    - If values is a non-empty list, filter for each distinct value using a
      correlated EXISTS against the json_each expansion, so the caller keeps
      "every requested value is present" semantics without multiplying outer
      model rows: a row's array elements matching more than once, or several
      requested values each matching, would otherwise duplicate the row in
      the outer query (one row per matching table-valued expansion), which
      also inflates count() and can push matching rows past a limit/offset
      page. Repeated requested values (e.g. ["a", "a"]) collapse to a single
      EXISTS clause since they add no additional constraint.
    - Each value is matched by exact equality against an array element, so
      element boundaries are respected (e.g. a filter of "admin" does not
      match an element of "superadministrator") and no LIKE wildcard
      characters are interpreted.
    - PostgreSQL's json_each()/json_each_text() only accept JSON objects, and
      the json type has no equality operator, so the empty-list match uses
      json_array_length() == 0 (via _ListjsonArrayLength) and the element
      match uses json_array_elements_text() (via _ListjsonEachValue) to
      expand the JSON array into comparable text values; SQLite keeps using
      json_each(). Both wrappers use dedicated GenericFunction names instead
      of func.json_array_length()/func.json_each() so a same-process import
      of sqlalchemy_utils (which registers its own, cache-incompatible
      json_array_length) cannot disable SQL compilation caching.
    """
    if values == []:
        return [_ListjsonArrayLength(model_column) == 0]
    filters = []
    for value in dict.fromkeys(values):
        elements = _ListjsonEachValue(model_column).table_valued("value")
        filters.append(
            select(literal(1)).select_from(elements).where(elements.c.value == value).exists()
        )
    return filters
