from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime


class CreatedAt(TypeDecorator):
    """
    Custom SQLAlchemy type to automatically set the default value to the current datetime for created_at column.

    次の仕様に沿う
    - 引数に何も渡されなければ、`datetime.now()` の値が入る事を保証
    - 引数に日付が渡されれば、その値が使われる事を保証
    """

    impl = DateTime
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value, dialect):
        if value is None:
            value = datetime.now()
        return value

    def process_result_value(self, value, dialect):
        return value
