"""Repository introspection helpers.

Pattern A (subclass without ``__init__``) と Pattern B (subclass が
``__init__`` を独自定義) の自動判定と、 適切な呼び出し規約での
インスタンス化ヘルパーを提供する。

Both BaseRepository and AsyncBaseRepository follow the same protocol:

- ``__init__(self, model=None, session=None)`` で model は型パラメータから自動推論
- サブクラスが ``__init__(self, session=...)`` 形で override することも許容

fast-domain などの consumer が repository クラスを動的にインスタンス化する
ときに、 上記 2 パターンを意識せず扱えるようにする。
"""

from __future__ import annotations

from typing import Any, Type, TypeVar, get_args


def resolve_repository_model(
    repository_class: type,
    *,
    require_concrete: bool = True,
) -> Type:
    """Resolve the model class declared as ``BaseRepository[Model]``.

    Args:
        repository_class: Repository subclass to inspect.
        require_concrete: When ``True``, skip unresolved ``TypeVar`` arguments.

    Raises:
        TypeError: No model type argument could be resolved.
    """
    if hasattr(repository_class, "__orig_bases__"):
        for base in repository_class.__orig_bases__:
            args = get_args(base)
            if args:
                potential_model = args[0]
                if require_concrete and isinstance(potential_model, TypeVar):
                    continue
                return potential_model

    raise TypeError(
        f"Could not resolve model from repository class {repository_class.__name__}"
    )


def get_model_from_repository_class(repository_class: type) -> Type:
    """``BaseRepository[Model]`` 形式の Generic 宣言から Model を取り出す。

    Args:
        repository_class: ``class Foo(BaseRepository[Model])`` のように
            Generic パラメータ付きで宣言された repository サブクラス。

    Returns:
        Generic パラメータに記録されているモデル型。

    Raises:
        TypeError: Generic パラメータが取得できない場合。
    """
    try:
        return resolve_repository_model(repository_class)
    except TypeError:
        raise TypeError(
            f"Could not extract model from {repository_class.__name__}; "
            "declare it as `class X(BaseRepository[Model])`."
        ) from None


def _uses_framework_init(repository_class: type) -> bool:
    """class が framework 提供の ``__init__`` のままなら True (= Pattern A)。"""
    from repom.repositories.async_base_repository import AsyncBaseRepository
    from repom.repositories.base_repository import BaseRepository

    return repository_class.__init__ in (
        BaseRepository.__init__,
        AsyncBaseRepository.__init__,
    )


def create_repository_instance(repository_class: type, session: Any):
    """Pattern A / B を自動判定して repository をインスタンス化する。

    - Pattern A: ``class UserRepository(BaseRepository[User])`` (``__init__`` なし)。
      ``repository_class(model, session)`` で呼び出す。
    - Pattern B: サブクラスが ``__init__(self, session=...)`` を独自定義。
      ``repository_class(session=session)`` で呼び出す。

    Args:
        repository_class: ``BaseRepository`` または ``AsyncBaseRepository``
            のサブクラス。
        session: Session / AsyncSession インスタンス。

    Returns:
        インスタンス化された repository。
    """
    if _uses_framework_init(repository_class):
        model = get_model_from_repository_class(repository_class)
        return repository_class(model, session)
    return repository_class(session=session)
