from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel


class SimpleRecord(BaseModel):
    __tablename__ = 'simple_repository_records'

    name: Mapped[str] = mapped_column(String(100), nullable=False)
