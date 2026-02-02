"""基本的なテストモデル

シンプルなモデルとリレーションシップの基本パターンを提供します。
"""

from repom.models.base_model import BaseModel
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


class User(BaseModel):
    """ユーザーモデル（テスト用）
    
    基本的な CRUD 操作のテストに使用します。
    """
    __tablename__ = 'test_users'
    
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    
    # リレーションシップ（後で定義）
    if TYPE_CHECKING:
        posts: Mapped[list['Post']]


class Post(BaseModel):
    """投稿モデル（テスト用）
    
    リレーションシップと外部キーのテストに使用します。
    """
    __tablename__ = 'test_posts'
    
    title: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(1000))
    user_id: Mapped[int] = mapped_column(ForeignKey('test_users.id'))
    
    # リレーションシップ
    user: Mapped['User'] = relationship(back_populates='posts')


# User にリレーションシップを追加
User.posts = relationship('Post', back_populates='user')
