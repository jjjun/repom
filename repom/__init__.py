"""repom - SQLAlchemy foundation package

このパッケージは、SQLAlchemy を使ったデータアクセス層の基盤を提供します。

Available Classes:
- BaseModel: SQLAlchemy モデルの基底クラス
- BaseModelAuto: Pydantic スキーマ自動生成機能付きモデル
- BaseRepository: 同期版リポジトリ
- AsyncBaseRepository: 非同期版リポジトリ
- FilterParams: 検索パラメータの基底クラス
- SoftDeletableMixin: 論理削除機能を追加する Mixin

Recommended Import Style (推奨):
    from repom import BaseRepository, AsyncBaseRepository
    from repom import FilterParams, SoftDeletableMixin
    from repom import BaseModel, BaseModelAuto
"""

# Core models
from repom.models import BaseModel, BaseModelAuto

# Repositories
from repom.repositories import BaseRepository, AsyncBaseRepository, FilterParams

# Mixins
from repom.mixins import SoftDeletableMixin

# Query Analysis
from repom.scripts.query_analyzer import QueryAnalyzer

__all__ = [
    # Models
    'BaseModel',
    'BaseModelAuto',
    # Repositories
    'BaseRepository',
    'AsyncBaseRepository',
    'FilterParams',
    # Mixins
    'SoftDeletableMixin',
    # Query Analysis
    'QueryAnalyzer',
]
