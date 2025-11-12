from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime


class ISO8601DateTime(TypeDecorator):
    """ISO 8601形式の日付時刻を扱うためのカスタムTypeDecoratorクラス"""
    impl = DateTime
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, datetime):
                return value.isoformat()
            else:
                raise ValueError("Value should be a datetime object.")
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return datetime.fromisoformat(value)
        return value
