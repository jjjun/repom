from sqlalchemy import (
    Column,
    String,
)
from sqlalchemy.orm import relationship
from mine_db.base_model import BaseModel
from mine_db.utility import get_plural_tablename


class WikiListModel(BaseModel):
    """...
    """
    __tablename__ = get_plural_tablename(__file__)

    title = Column(String(255), nullable=False, default='')
    detail_url = Column(String(255), nullable=False, default='')

    wiki_group = relationship(
        'WikiGroupModel',
        back_populates='wiki_lists',
        uselist=False,
    )
