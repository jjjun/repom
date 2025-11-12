from sqlalchemy import (
    Column,
    String,
    Date,
)
from datetime import datetime

from mine_db.base_model import BaseModel
from mine_db.utility import get_plural_tablename


class SampleModel(BaseModel):
    """...
    """
    __tablename__ = get_plural_tablename(__file__)
    # True にすると、自動で created_at が追加される
    # defaultでは created_at を使用しない
    use_created_at = True

    # default='' と nullable=False は冗長な書き方で、省略しても問題ない。
    # ただ、nullable=False を指定する事でデータベースレベルでの制約を強制できる。
    value = Column(String(255), nullable=False, default='')
    done_at = Column(Date)

    def done(self):
        """
        done_atに今日の日付を代入する関数
        """
        self.done_at = datetime.now().date()
        return self

    # もし init を使いたいなら、上記のプロパティをすべて手動で self.xxx = '' しなくてはいけないみたい
    # def __init__(self):
    #     pass

    # def __repr__(self):
    #     return '<message %r>' % (self.message)
