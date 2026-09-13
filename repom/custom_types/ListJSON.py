from sqlalchemy.types import TypeDecorator, JSON
from sqlalchemy import func
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


def listjson_filter(model_column, values):
    """
    Generate SQLAlchemy filter conditions for ListJSON columns.
    - If values == [], filter for empty lists.
    - If values is a non-empty list, filter for each value using json_each.
    - Each value is matched by exact equality against an array element, so
      element boundaries are respected (e.g. a filter of "admin" does not
      match an element of "superadministrator") and no LIKE wildcard
      characters are interpreted.
    """
    if values == []:
        return [model_column == []]
    filters = []
    for value in values:
        fields_func = func.json_each(model_column).table_valued("value", joins_implicitly=True)
        filters.append(fields_func.c.value == value)
    return filters
