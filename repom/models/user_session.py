"""
User session model without id column.
Uses composite primary key (user_id, session_token) instead.
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from repom.base_model_auto import BaseModelAuto


class UserSession(BaseModelAuto, use_id=False):
    """
    User session tracking model with composite primary key.
    This model demonstrates use_id=False to avoid auto-generated id column.
    """

    __tablename__ = 'user_sessions'

    # Composite primary key
    user_id = Column(Integer, primary_key=True, nullable=False)
    session_token = Column(String(64), primary_key=True, nullable=False)

    # Session data
    ip_address = Column(String(45))  # IPv6 max length
    user_agent = Column(String(255))
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime)
