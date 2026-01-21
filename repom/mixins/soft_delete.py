"""Soft delete functionality for SQLAlchemy models

このモジュールは、SQLAlchemy モデルに論理削除機能を追加する Mixin を提供します。
"""

from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
import logging

logger = logging.getLogger(__name__)


class SoftDeletableMixin:
    """論理削除機能を提供する Mixin

    このクラスを継承することで、モデルに論理削除機能を追加できます。
    論理削除されたレコードは deleted_at に削除日時が記録され、
    通常のクエリでは自動的に除外されます。

    使用方法:
        from repom.mixins import SoftDeletableMixin
        from repom.models.base_model_auto import BaseModelAuto

        class MyModel(BaseModelAuto, SoftDeletableMixin):
            __tablename__ = "my_table"
            # ... other fields

    提供される機能:
        - deleted_at カラムの自動追加（インデックス付き）
        - soft_delete() メソッド: 論理削除を実行
        - restore() メソッド: 削除を取り消し
        - is_deleted プロパティ: 削除済みかどうかを確認

    注意:
        - deleted_at は UTC タイムゾーン付きの DateTime 型です
        - セッションへの追加やコミットは呼び出し側で行う必要があります
        - BaseRepository を使用すると、削除済みレコードの自動除外が有効になります
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,  # パフォーマンス向上のためインデックスを作成
        info={'description': '論理削除日時（NULL = 削除されていない）'}
    )

    def soft_delete(self) -> None:
        """論理削除を実行

        deleted_at に現在時刻（UTC）を設定します。
        セッションへの追加やコミットは呼び出し側で行う必要があります。

        使用例:
            item = repo.get_by_id(1)
            item.soft_delete()
            session.commit()
        """
        self.deleted_at = datetime.now(timezone.utc)
        logger.info(f"Soft deleted: {self.__class__.__name__} id={getattr(self, 'id', 'N/A')}")

    def restore(self) -> None:
        """削除を取り消し

        deleted_at を NULL に戻します。
        セッションへの追加やコミットは呼び出し側で行う必要があります。

        使用例:
            item = repo.get_by_id_with_deleted(1)
            if item and item.is_deleted:
                item.restore()
                session.commit()
        """
        self.deleted_at = None
        logger.info(f"Restored: {self.__class__.__name__} id={getattr(self, 'id', 'N/A')}")

    @property
    def is_deleted(self) -> bool:
        """削除済みかどうかを返す

        Returns:
            bool: deleted_at が設定されている場合 True
        """
        return self.deleted_at is not None
