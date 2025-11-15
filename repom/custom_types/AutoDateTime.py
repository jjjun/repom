from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime


class AutoDateTime(TypeDecorator):
    """
    Custom SQLAlchemy type to automatically set datetime values on insert.

    自動的に日時を設定するカスタム型:
    - 引数に何も渡されなければ、`datetime.now()` の値が入る事を保証
    - 引数に日付が渡されれば、その値が使われる事を保証

    使用例:
        created_at = Column(AutoDateTime, nullable=False)
        updated_at = Column(AutoDateTime, nullable=False)

    注意:
        updated_at の自動更新は SQLAlchemy Event で実装されています
        （BaseModel の @event.listens_for を参照）
    """

    impl = DateTime
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value, dialect):
        if value is None:
            value = datetime.now()
        return value

    def process_result_value(self, value, dialect):
        return value
