from sqlalchemy import (
    Column,
    String,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import validates
from mine_db.base_model import BaseModel
from mine_db.utility import get_plural_tablename


class WikiRevModel(BaseModel):
    """
    """
    __tablename__ = get_plural_tablename(__file__)

    key = Column(String(255), nullable=False, unique=True)
    title = Column(String(255), nullable=False, default='')
    content = Column(Text)
    status = Column(String(255), nullable=False, default='waiting')

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('waiting', 'reject', 'merged'):
            raise ValueError("Invalid status value")
        return value

    __table_args__ = (
        CheckConstraint("key != ''", name='check_key_not_empty'),
        CheckConstraint("url != ''", name='check_url_not_empty'),
    )
