"""親モデル - ModelA"""
from sqlalchemy import String
from sqlalchemy.orm import relationship, mapped_column, Mapped
from typing import TYPE_CHECKING, List
from repom import BaseModelAuto

if TYPE_CHECKING:
    from ..package_b.model_b import ModelB


class ModelA(BaseModelAuto, use_created_at=True):
    """親モデル（AniVideoItemModel に相当）"""
    __tablename__ = 'test_model_a'

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 文字列参照による relationship
    # ※ ModelB がまだ定義されていない可能性がある
    children: Mapped[List["ModelB"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
