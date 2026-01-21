from sqlalchemy.types import TypeDecorator, TEXT


class StrEncodedArray(TypeDecorator):
    """
    配列を , 区切りで文字列にしてDBに格納するカスタムカラムタイプ
    この型を使うよりも、ListJSONの方を推奨
    """

    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = ','.join(filter(None, map(str, value)))
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            value = []
        else:
            value = [item for item in value.split(",") if item]
        return value
