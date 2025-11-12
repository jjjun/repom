from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Date,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from mine_db.custom_types.ListJSON import ListJSON
from mine_db.base_model import BaseModel
from mine_db.utility import get_plural_tablename


class WikiListModel(BaseModel):
    """
    """
    __tablename__ = get_plural_tablename(__file__)
    use_created_at = True

    detail_url = Column(String(255), nullable=False, default='')
    title = Column(String(255), nullable=False)
    # 制作会社
    studio_names = Column(ListJSON)
    # 放送局
    broadcaster_names = Column(ListJSON)
    # 開始日
    started_at = Column(Date)
    # 終了日
    finished_at = Column(Date)
    # number_of_episodes: 正しい表現で、エピソードの数を示す際に使う
    number_of_episodes = Column(Integer)
    # 特別編
    is_special_episode = Column(Boolean, nullable=False, default=False)

    wiki_detail = relationship(
        'WikiDetailModel',
        back_populates='wiki_list',
        uselist=False
    )

    __table_args__ = (
        CheckConstraint("title != ''", name='title_not_empty'),
    )
