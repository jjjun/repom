"""repom.models - SQLAlchemy model base classes

このモジュールは、SQLAlchemy モデルの基底クラスを提供します。

Available Classes:
- BaseModel: SQLAlchemy モデルの基底クラス
- Base: SQLAlchemy の DeclarativeBase（database.py から再エクスポート）

Recommended Import Style (推奨):
    from repom import BaseModel
    from repom.models import BaseModel  # 直接インポートも可能
"""

from repom.models.base_model import BaseModel, Base

__all__ = [
    'BaseModel',
    'Base',
]
