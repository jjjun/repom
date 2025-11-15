"""
User session model without id column.
Uses composite primary key (user_id, session_token) instead.
"""

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from repom.base_model_auto import BaseModelAuto


class UserSession(BaseModelAuto, use_id=False):
    """
    User session tracking model with composite primary key.
    This model demonstrates use_id=False to avoid auto-generated id column.
    """

    __tablename__ = 'user_sessions'

    # Composite primary key
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)

    # Session data
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime)
