from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime, timezone


class AutoDateTime(TypeDecorator):
    """
    Custom SQLAlchemy type to automatically set datetime values on insert.

    自動的に日時を設定するカスタム型:
    - 引数に何も渡されなければ、`datetime.now()` の値が入る事を保証
    - 引数に日付が渡されれば、その値が使われる事を保証

    使用例:
        from sqlalchemy.orm import Mapped, mapped_column

        created_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)

    注意:
        updated_at の自動更新は SQLAlchemy Event で実装されています
        （BaseModel の @event.listens_for を参照）
    """

    impl = DateTime(timezone=True)
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value, dialect):
        if value is None:
            value = datetime.now(timezone.utc)
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
