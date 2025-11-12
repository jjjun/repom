from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from mine_db.base_model import BaseModel
from mine_db.utility import get_plural_tablename


class WikiDetailModel(BaseModel):
    """
    """
    __tablename__ = get_plural_tablename(__file__)
    use_created_at = True

    content_filepath = Column(String(255), nullable=False, default='')

    title = Column(String(255), nullable=False, default='')
    # wikiのapiで使うid
    page_id = Column(Integer, nullable=True)
    # 実行した日時(content_filepathのファイルが作成された日時)
    executed_at = Column(DateTime, nullable=True)
    # クロールするかどうか
    is_crawl_enabled = Column(Boolean, nullable=False, default=True)
    # URLが有効かどうか
    is_url_valid = Column(Boolean, nullable=False, default=True)

    wiki_list_id = Column(Integer, ForeignKey('wiki_lists.id'), nullable=False)
    wiki_list = relationship(
        'WikiListModel',
        back_populates='ani_wiki_tv_detail',
        uselist=False
    )

    __table_args__ = (
        CheckConstraint("title != ''", name='title_not_empty'),
    )
