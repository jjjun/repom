from datetime import datetime, timezone

from repom.custom_types.UTCDateTime import UTCDateTime


class AutoDateTime(UTCDateTime):
    """
    Custom SQLAlchemy type to automatically set datetime values on insert.

    自動的に日時を設定するカスタム型:
    - 引数に何も渡されなければ、`datetime.now()` の値が入る事を保証
    - 引数に日付が渡されれば、その値が使われる事を保証

    タイムゾーンの正規化（書き込み時）:
    - tzinfo 付きの値は `astimezone(timezone.utc)` で UTC に変換してから書き込む
      （SQLite のようにオフセットを保持しないバックエンドでも瞬時 (instant) を
      変えずに保存するため）
    - naive な値は UTC とみなし、`replace(tzinfo=timezone.utc)` で tzinfo を
      付与するだけで、値（wall time）は変更しない
    - 読み込み時（process_result_value）は UTC に正規化して返す

    使用例:
        from sqlalchemy.orm import Mapped, mapped_column

        created_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)

    注意:
        updated_at の自動更新は SQLAlchemy Event で実装されています
        （BaseModel の @event.listens_for を参照）
    """

    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value, dialect):
        if value is None:
            value = datetime.now(timezone.utc)
        return super().process_bind_param(value, dialect)
