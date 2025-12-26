"""Mixin classes for SQLAlchemy models

このモジュールは、SQLAlchemy モデルに追加機能を提供する Mixin クラスを含みます。

Available Mixins:
- SoftDeletableMixin: 論理削除機能を提供
"""

from repom.mixins.soft_delete import SoftDeletableMixin

__all__ = ['SoftDeletableMixin']
