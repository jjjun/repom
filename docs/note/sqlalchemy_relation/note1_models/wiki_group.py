from sqlalchemy import (
    Column,
    String,
)
from sqlalchemy.orm import relationship
from mine_db.base_model import BaseModel
from mine_db.utility import get_plural_tablename


class WikiGroupModel(BaseModel):
    """...
    """
    __tablename__ = get_plural_tablename(__file__)

    url = Column(String(255), nullable=False, unique=True)

    wiki_lists = relationship(
        'WikiListModel',
        back_populates='wiki_group',
        cascade="all, delete-orphan"
    )
