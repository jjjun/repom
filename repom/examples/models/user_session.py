"""
User session model without id column.
Uses composite primary key (user_id, session_token) instead.

このモデルは use_id=False を使用した複合主キーの例を示しています。
"""

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from repom.base_model_auto import BaseModelAuto


class UserSession(BaseModelAuto, use_id=False, use_created_at=True, use_updated_at=True):
    """
    User session tracking model with composite primary key.
    This model demonstrates use_id=False to avoid auto-generated id column.

    推奨構造:
    - use_id=False で複合主キーを使用
    - パラメータ方式で明示的に指定
    - info メタデータで description を記述
    """

    __tablename__ = 'user_sessions'

    # Composite primary key
    user_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        nullable=False,
        info={'description': 'ユーザーID'}
    )
    session_token: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        nullable=False,
        info={'description': 'セッショントークン'}
    )

    # Session data
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        info={'description': 'IPアドレス（IPv6対応）'}
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        info={'description': 'ユーザーエージェント'}
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        info={'description': '有効期限'}
    )
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        info={'description': '最終アクティビティ'}
    )
