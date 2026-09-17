from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime


class ISO8601DateTime(TypeDecorator):
    """dialect のネイティブ DateTime カラムとして日付時刻を保存するカスタム
    TypeDecorator クラス（ISO 8601 文字列としては保存しない）。

    bind 時は datetime 値をそのまま渡し（None は None のまま、それ以外の型は
    ValueError）、読み込み時も dialect が返す datetime 値をそのまま返す。
    driver が str を返した場合のみ datetime.fromisoformat() でパースする。

    カラムを ISO 8601 文字列として保存したい場合は ISO8601DateTimeStr を使用する
    （docs/guides/model/system_columns_and_custom_types.md 参照）。
    """
    impl = DateTime
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, datetime):
                return value
            else:
                raise ValueError("Value should be a datetime object.")
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value
