"""同期/非同期で共通するリポジトリ基底クラス.

`BaseRepository` と `AsyncBaseRepository` はほぼ構造が同一で、
差分は ``async def`` / ``await`` / ``AsyncSession`` の有無だけです。
本モジュールは、その中でも await を一切必要としない
（同期/非同期に依存しない）メンバーを 1 箇所に集約します:

- ``__init__`` の骨格（セッション種別ガードのみサブクラスが差し替える）
- ``_infer_model_from_type_params``（型パラメータからのモデル推論）
- ``session`` プロパティ / セッター
- ``_has_soft_delete``
- ``_bulk_filters``

I/O を伴うメソッド（``find`` / ``save`` など）は await ポイントが
異なるため各サブクラスに残します。
"""

import inspect
import warnings
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import ColumnElement

from repom.repositories._core import has_soft_delete
from repom.repositories._introspection import resolve_repository_model

T = TypeVar('T')


class RepositoryBase(Generic[T]):
    """同期/非同期に依存しない共通メンバーを保持する基底クラス。

    ``BaseRepository`` / ``AsyncBaseRepository`` が継承します。
    セッション種別のガード（``model`` 引数に Session/AsyncSession が
    渡されていないかの検出）はサブクラスがクラス属性で差し替えます。
    """

    # ``model`` 引数に渡されたら拒否するセッション型（サブクラスで設定）
    _session_reject_types: tuple = ()
    # 上記に該当した場合に送出する TypeError のメッセージ（サブクラスで設定）
    _session_reject_message: str = ""
    # _infer_model_from_type_params のガイダンス表示に使う基底クラス名
    _repository_base_name: str = "BaseRepository"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        find = cls.__dict__.get("find")
        if find is None:
            return

        parameters = inspect.signature(find).parameters
        # include_deleted may be correctly forwarded through **kwargs.
        if "filters" not in parameters:
            warnings.warn(
                f"{cls.__name__}.find() should accept and merge filters "
                "to preserve the BaseRepository find() contract.",
                RuntimeWarning,
                stacklevel=2,
            )

    def __init__(self, model: Optional[Type[T]] = None, session=None):
        """リポジトリの初期化

        Args:
            model (Type[T], optional): モデルクラス. 省略時は型パラメータから自動推論される.
            session: データベースセッション. Defaults to None（内部セッションを使用）.

        Raises:
            TypeError: model が推論できない場合、または Session/AsyncSession が
                model に渡された場合。
        """
        # Session が model 引数に渡された場合の検出（位置引数で渡された場合）
        if self._session_reject_types and isinstance(model, self._session_reject_types):
            raise TypeError(self._session_reject_message)

        # model が明示的に指定されていない場合、型パラメータから推論
        if model is None:
            model = self._infer_model_from_type_params()

        self.model = model
        self._session_override = session
        self._scoped_session = None
        self.default_options: List = []  # デフォルトの eager loading options

    @classmethod
    def _infer_model_from_type_params(cls) -> Type[T]:
        """Infer the model class from the repository generic parameter."""
        try:
            return resolve_repository_model(cls)
        except TypeError:
            base = cls._repository_base_name
            raise TypeError(
                f"Could not infer model type for {cls.__name__}. "
                f"Please either:\n"
                f"1. Specify model explicitly: {cls.__name__}(model=YourModel, session=...)\n"
                f"2. Define class as: class {cls.__name__}({base}[YourModel])\n"
                f"3. Override __init__ and call super().__init__(YourModel, session)"
            ) from None

    @property
    def session(self):
        """明示的に渡されたセッション（またはスコープ内の内部セッション）を返却"""
        return self._session_override or self._scoped_session

    @session.setter
    def session(self, session) -> None:
        """明示的セッションを設定（None でリセット）"""
        self._session_override = session

    def _has_soft_delete(self) -> bool:
        """モデルが SoftDeletableMixin を持つか確認

        Returns:
            bool: deleted_at カラムが存在する場合 True
        """
        return has_soft_delete(self.model)

    def _bulk_filters(self, filter_by: Optional[dict]) -> list[ColumnElement]:
        if not filter_by:
            return []

        filters = []
        for column_name, value in filter_by.items():
            if not hasattr(self.model, column_name):
                raise AttributeError(f"Column '{column_name}' does not exist on {self.model.__name__}")
            filters.append(getattr(self.model, column_name) == value)
        return filters
