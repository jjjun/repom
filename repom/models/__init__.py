"""repom.models - SQLAlchemy model base classes

このモジュールは、SQLAlchemy モデルの基底クラスを提供します。

Available Classes:
- BaseModel: SQLAlchemy モデルの基底クラス
- BaseModelAuto: Pydantic スキーマ自動生成機能付きモデル
- BaseStaticModel: 静的マスターデータ用モデル
- Base: SQLAlchemy の DeclarativeBase（database.py から再エクスポート）

Recommended Import Style (推奨):
    from repom import BaseModel, BaseModelAuto
    from repom.models import BaseModel, BaseModelAuto  # 直接インポートも可能
"""

from repom.models.base_model import BaseModel, Base
from repom.models.base_model_auto import BaseModelAuto, SchemaGenerationError
from repom.models.base_static import BaseStaticModel

__all__ = [
    'BaseModel',
    'BaseModelAuto',
    'BaseStaticModel',
    'Base',
    'SchemaGenerationError',
]
