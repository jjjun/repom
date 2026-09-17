"""同期/非同期で共通するリポジトリ基底クラス.

`BaseRepository` と `AsyncBaseRepository` はほぼ構造が同一で、
差分は ``async def`` / ``await`` / ``AsyncSession`` の有無だけです。
本モジュールは、その中でも await を一切必要としない
（同期/非同期に依存しない）メンバーを 1 箇所に集約します:

- ``__init__`` の骨格（セッション種別ガードのみサブクラスが差し替える）
- ``_infer_model_from_type_params``（型パラメータからのモデル推論）
- ``session`` プロパティ / セッター
- ``_has_soft_delete``
- ``_bulk_filters`` / ``_resolve_column`` / ``_resolve_equality_filter`` /
  ``_resolve_ids_filter``

I/O を伴うメソッド（``find`` / ``save`` など）は await ポイントが
異なるため各サブクラスに残します。
"""

import contextvars
import inspect
import warnings
from collections.abc import Sequence
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import ClauseElement, ColumnElement, inspect as sa_inspect
from sqlalchemy.orm import QueryableAttribute

from repom.repositories._core import has_soft_delete
from repom.repositories._introspection import resolve_repository_model

T = TypeVar('T')


class RepositoryBase(Generic[T]):
    """同期/非同期に依存しない共通メンバーを保持する基底クラス。

    ``BaseRepository`` / ``AsyncBaseRepository`` が継承します。
    セッション種別のガード（``model`` 引数に Session/AsyncSession が
    渡されていないかの検出）はサブクラスがクラス属性で差し替えます。

    スレッド/タスク安全性:
        ``session`` を明示せずに構築したインスタンスは、複数のリクエスト・
        タスク・スレッドで共有しても安全です。``_session_scope()`` が内部で
        開くセッションは ``contextvars.ContextVar`` に保持されるため、
        タスク/スレッドごとに独立した値を持ち、他の呼び出し元のセッション・
        未コミットの変更・identity map を参照することはありません。
        ``session`` を明示したインスタンスは、その呼び出し元が所有する
        セッションに紐づくため、そのセッションを複数タスクで同時利用しない
        という通常の SQLAlchemy の制約がそのまま適用されます。
    """

    # ``model`` 引数に渡されたら拒否するセッション型（サブクラスで設定）
    _session_reject_types: tuple = ()
    # 上記に該当した場合に送出する TypeError のメッセージ（サブクラスで設定）
    _session_reject_message: str = ""
    # _infer_model_from_type_params のガイダンス表示に使う基底クラス名
    _repository_base_name: str = "BaseRepository"

    # get_by / _bulk_filters が受け付けるカラム名のホワイトリスト。
    # None の場合はマップされた全カラムを許可する（サブクラスで上書き可能、
    # allowed_order_columns と同様の仕組み）。
    allowed_filter_columns: Optional[List[str]] = None

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
        # _session_scope() が内部で開いたセッションを保持する。プレーンな
        # インスタンス属性にすると、同一インスタンスを複数タスク/スレッドで
        # 共有した際に他の呼び出し元のセッションを取り合ってしまう
        # （タスク/スレッドごとに独立した値を持てる contextvars を使う理由）。
        self._scoped_session_var: contextvars.ContextVar = contextvars.ContextVar(
            f"{type(self).__name__}._scoped_session"
        )
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
    def _scoped_session(self):
        """現在のタスク/スレッドで ``_session_scope()`` が開いた内部セッション。

        ``_scoped_session_var`` は contextvars 経由のため、値の設定/解除は
        ``_session_scope()`` 側で ``set()`` / ``reset(token)`` を使って行う。
        ここは読み取り専用のアクセサ。
        """
        return self._scoped_session_var.get(None)

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

    def _append_soft_delete_filter(self, filters: list, include_deleted: bool = False) -> None:
        """論理削除フィルタ（deleted_at IS NULL）を filters に追加する（in-place）

        モデルが論理削除に対応し、かつ include_deleted が False の場合のみ
        追加する。find / count / find_by_ids / bulk_delete など、論理削除
        フィルタを組み立てる全ての箇所で共通して使う。

        Args:
            filters (list): フィルタ条件のリスト。ここに直接追加する。
            include_deleted (bool): 削除済みレコードも含めるか（デフォルト: False）
        """
        if self._has_soft_delete() and not include_deleted:
            filters.append(self.model.deleted_at.is_(None))

    def _uses_internal_session(self, session) -> bool:
        """``session`` が ``_session_scope()`` の内部生成セッションか判定する。

        True の場合のみ commit/rollback の責任を repository 側が持つ。
        呼び出し元が明示的に渡した（または呼び出し元のスコープで既に開かれて
        いる）外部セッションの場合は False を返し、commit/rollback は呼び出し
        元に委ねる。save / saves / remove などの書き込み系メソッドと
        soft_delete / restore / permanent_delete で共通に使うためのヘルパー。

        Returns:
            bool: 内部セッションの場合 True
        """
        return self._session_override is None and self._scoped_session is session

    def _bulk_filters(self, filter_by: Optional[dict]) -> list[ColumnElement]:
        if not filter_by:
            return []

        return [self._resolve_equality_filter(column_name, value) for column_name, value in filter_by.items()]

    def _resolve_column(self, column_name: str) -> ColumnElement:
        """caller-supplied column name をマップされたカラム属性に解決する。

        hasattr/getattr は relationship・hybrid property・メソッド・dunder
        など、マップされたカラムでない属性にも一致してしまう。ここでは
        ``sqlalchemy.inspect(self.model).columns`` に対して照合することで、
        実在するマップドカラムのみを許可する。``allowed_filter_columns`` が
        設定されている場合は、そのホワイトリストに含まれるカラムのみを
        さらに許可する（``allowed_order_columns`` と同じ設計）。

        Args:
            column_name: 検索・更新条件に使うカラム名。信頼できる識別子で
                あることが前提であり、リクエスト由来の値をそのまま渡す
                場合は ``allowed_filter_columns`` を設定すること。

        Raises:
            AttributeError: column_name がマップされたカラムでない場合、
                または allowed_filter_columns によって許可されていない場合。
        """
        mapper = sa_inspect(self.model)
        if column_name not in mapper.columns:
            raise AttributeError(f"Unknown column on {self.model.__name__}")

        if self.allowed_filter_columns is not None and column_name not in self.allowed_filter_columns:
            raise AttributeError(f"Unknown column on {self.model.__name__}")

        return getattr(self.model, column_name)

    def _resolve_equality_filter(self, column_name: str, value: Any) -> ColumnElement:
        """``_resolve_column`` で解決したカラムから等価フィルタ式を組み立てる。

        マップされたカラムであっても、生成された式が ``ColumnElement`` に
        ならないケースを防ぐための最終防御として、``column == value`` の
        結果を検証する。例えば ``__tablename__`` のような素の文字列属性は
        本来 mapper.columns に含まれず ``_resolve_column`` で弾かれるが、
        万一すり抜けた場合でも Python の bool 評価にフォールバックさせず
        例外にする。
        """
        column = self._resolve_column(column_name)
        predicate = column == value
        if not isinstance(predicate, ColumnElement):
            raise AttributeError(f"Unknown column on {self.model.__name__}")

        return predicate

    def _resolve_ids_filter(self, ids: Sequence[Any]) -> ColumnElement:
        """``bulk_delete`` の ``ids`` からマップされた ``id`` カラムの IN 条件を組み立てる。

        ``Column.in_()`` は要素が ``ClauseElement``（SQL 式）や
        ``QueryableAttribute``（``Model.column`` のような ORM 属性、
        ``__clause_element__()`` で ``ClauseElement`` に解決される）の場合、
        バインドパラメータではなく SQL 式としてそのまま埋め込む。例えば
        ``Model.id.in_([Model.other_column])`` は ``id IN (other_column)`` に
        コンパイルされ、値の比較ではなくカラム同士の比較になる。``ids`` は
        スカラー値の列挙である前提のため、これらが紛れ込んでいる場合は式の
        混入とみなして拒否する。

        Raises:
            AttributeError: モデルに ``id`` カラムが存在しない場合。
            TypeError: ``ids`` に SQL 式や ORM 属性が含まれる場合。
        """
        mapper = sa_inspect(self.model)
        if "id" not in mapper.columns:
            raise AttributeError(f"Column 'id' does not exist on {self.model.__name__}")

        for value in ids:
            if isinstance(value, (ClauseElement, QueryableAttribute)):
                raise TypeError(f"ids must contain plain values, not SQL expressions: {value!r}")

        return self.model.id.in_(ids)
