import pytest
from mine_db.base_model import BaseModel


class Sample1Model(BaseModel):
    __tablename__ = 'sample_model'
