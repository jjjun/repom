"""repom - SQLAlchemy foundation package

このパッケージは、SQLAlchemy を使ったデータアクセス層の基盤を提供します。

Available Classes:
- BaseModel: SQLAlchemy モデルの基底クラス
- BaseModelAuto: Pydantic スキーマ自動生成機能付きモデル
- BaseRepository: 同期版リポジトリ
- AsyncBaseRepository: 非同期版リポジトリ
- FilterParams: 検索パラメータの基底クラス
- SoftDeletableMixin: 論理削除機能を追加する Mixin

Backward Compatibility:
以下のインポートパスは後方互換性のために維持されています：
    from repom import BaseRepository, AsyncBaseRepository
    from repom import FilterParams, SoftDeletableMixin
    from repom import BaseModel, BaseModelAuto

推奨される新しいインポートパス：
    from repom.repositories import BaseRepository, AsyncBaseRepository, FilterParams
    from repom.mixins import SoftDeletableMixin
    from repom.base_model import BaseModel
    from repom.base_model_auto import BaseModelAuto
"""

# Core models
from repom.base_model import BaseModel
from repom.base_model_auto import BaseModelAuto

# Repositories
from repom.repositories import BaseRepository, AsyncBaseRepository, FilterParams

# Mixins
from repom.mixins import SoftDeletableMixin

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
]
