"""Many-to-many relationship helpers for SQLAlchemy models."""

from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import object_session

TTarget = TypeVar("TTarget")


class ManyToManyMixin:
    """Mixin with generic helpers for link-table many-to-many relations.

    The model instance must already be persisted or flushed so ``self.id`` is
    populated before calling ``add_related_item``. These helpers add and flush
    target/link rows, but committing remains the caller's responsibility.
    """

    def add_related_item(
        self,
        data: dict[str, Any],
        target_model_class: type[TTarget],
        link_model_class: type[Any],
        self_foreign_key: str,
        target_foreign_key: str,
        lookup_fields: list[str],
    ) -> TTarget:
        """Create or find a target row, ensure the link exists, and return it."""
        session = object_session(self)
        if session is None:
            raise ValueError("ManyToManyMixin requires the model to be attached to a session.")

        self_id = getattr(self, "id", None)
        if self_id is None:
            raise ValueError("ManyToManyMixin requires self.id to be populated.")

        filters = [
            getattr(target_model_class, field) == data[field]
            for field in lookup_fields
        ]
        target = session.scalars(select(target_model_class).where(*filters)).first()

        if target is None:
            target = target_model_class(**data)
            session.add(target)
            session.flush()

        link = self._find_link(
            link_model_class=link_model_class,
            self_foreign_key=self_foreign_key,
            self_id=self_id,
            target_foreign_key=target_foreign_key,
            target_id=getattr(target, "id"),
        )
        if link is None:
            session.add(
                link_model_class(
                    **{
                        self_foreign_key: self_id,
                        target_foreign_key: getattr(target, "id"),
                    }
                )
            )
            session.flush()

        return target

    def remove_related_item(
        self,
        item_id: Any,
        link_model_class: type[Any],
        self_foreign_key: str,
        target_foreign_key: str,
    ) -> bool:
        """Remove a link row for this model and the target item."""
        session = object_session(self)
        if session is None:
            raise ValueError("ManyToManyMixin requires the model to be attached to a session.")

        self_id = getattr(self, "id", None)
        if self_id is None:
            raise ValueError("ManyToManyMixin requires self.id to be populated.")

        link = self._find_link(
            link_model_class=link_model_class,
            self_foreign_key=self_foreign_key,
            self_id=self_id,
            target_foreign_key=target_foreign_key,
            target_id=item_id,
        )
        if link is None:
            return False

        session.delete(link)
        session.flush()
        return True

    def _find_link(
        self,
        link_model_class: type[Any],
        self_foreign_key: str,
        self_id: Any,
        target_foreign_key: str,
        target_id: Any,
    ) -> Any | None:
        session = object_session(self)
        if session is None:
            raise ValueError("ManyToManyMixin requires the model to be attached to a session.")

        return session.scalars(
            select(link_model_class).where(
                getattr(link_model_class, self_foreign_key) == self_id,
                getattr(link_model_class, target_foreign_key) == target_id,
            )
        ).first()
