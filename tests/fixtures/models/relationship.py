"""リレーションシップテスト用モデル

複雑なリレーションシップパターン（親子関係、多対多など）のテストに使用します。
"""

from repom.models.base_model import BaseModel
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


class Parent(BaseModel):
    """親モデル（リレーションシップテスト用）

    一対多リレーションシップのテストに使用します。
    """
    __tablename__ = 'test_parents'

    name: Mapped[str] = mapped_column(String(100))

    # リレーションシップ
    children: Mapped[list['Child']] = relationship(back_populates='parent', cascade='all, delete-orphan')


class Child(BaseModel):
    """子モデル（リレーションシップテスト用）

    多対一リレーションシップのテストに使用します。
    """
    __tablename__ = 'test_children'

    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[int] = mapped_column(ForeignKey('test_parents.id'))

    # リレーションシップ
    parent: Mapped['Parent'] = relationship(back_populates='children')
