"""子モデル - ModelB"""
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import relationship, mapped_column, Mapped
from typing import TYPE_CHECKING
from repom import BaseModelAuto

if TYPE_CHECKING:
    from ..package_a.model_a import ModelA


class ModelB(BaseModelAuto, use_created_at=True):
    """子モデル（AniVideoUserStatusModel に相当）"""
    __tablename__ = 'test_model_b'

    parent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('test_model_a.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # 逆参照（back_populates）
    parent: Mapped["ModelA"] = relationship(
        back_populates="children"
    )
