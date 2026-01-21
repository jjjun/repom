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
        if value is None:
            return json.dumps([])
        if not isinstance(value, list):
            raise ValueError("Expected a list, but got a different type")
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        result = json.loads(value)
        if not isinstance(result, list):
            raise ValueError("Expected a list, but got a different type")
        return result


def listjson_filter(model_column, values):
    """
    Generate SQLAlchemy filter conditions for ListJSON columns.
    - If values == [], filter for empty lists.
    - If values is a non-empty list, filter for each value using json_each.
    """
    if values == []:
        return [model_column == []]
    filters = []
    for value in values:
        fields_func = func.json_each(model_column).table_valued("value", joins_implicitly=True)
        filters.append(fields_func.c.value.contains(value))
    return filters
