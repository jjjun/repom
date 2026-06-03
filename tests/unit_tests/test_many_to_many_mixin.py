from tests._init import *

from sqlalchemy import Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from repom.mixins import ManyToManyMixin
from repom.models.base_model import BaseModel


class ManyToManyOwnerModel(BaseModel, ManyToManyMixin):
    __tablename__ = "many_to_many_owner"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class ManyToManyTargetModel(BaseModel):
    __tablename__ = "many_to_many_target"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)


class ManyToManyLinkModel(BaseModel):
    __tablename__ = "many_to_many_link"

    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)


def _create_owner(db_test, name: str = "owner") -> ManyToManyOwnerModel:
    owner = ManyToManyOwnerModel(name=name)
    db_test.add(owner)
    db_test.flush()
    return owner


def _link_count(db_test, owner_id: int, target_id: int) -> int:
    return db_test.scalar(
        select(func.count()).select_from(ManyToManyLinkModel).where(
            ManyToManyLinkModel.owner_id == owner_id,
            ManyToManyLinkModel.target_id == target_id,
        )
    )


def test_add_related_item_creates_new_target_and_link(db_test):
    owner = _create_owner(db_test)

    target = owner.add_related_item(
        data={"name": "Target A", "slug": "target-a"},
        target_model_class=ManyToManyTargetModel,
        link_model_class=ManyToManyLinkModel,
        self_foreign_key="owner_id",
        target_foreign_key="target_id",
        lookup_fields=["slug"],
    )

    assert target.id is not None
    assert target.name == "Target A"
    assert _link_count(db_test, owner.id, target.id) == 1


def test_add_related_item_links_existing_unlinked_target(db_test):
    owner = _create_owner(db_test)
    existing = ManyToManyTargetModel(name="Existing", slug="existing")
    db_test.add(existing)
    db_test.flush()

    target = owner.add_related_item(
        data={"name": "Ignored", "slug": "existing"},
        target_model_class=ManyToManyTargetModel,
        link_model_class=ManyToManyLinkModel,
        self_foreign_key="owner_id",
        target_foreign_key="target_id",
        lookup_fields=["slug"],
    )

    assert target is existing
    assert target.name == "Existing"
    assert _link_count(db_test, owner.id, existing.id) == 1


def test_add_related_item_returns_existing_target_when_already_linked(db_test):
    owner = _create_owner(db_test)
    existing = ManyToManyTargetModel(name="Existing", slug="existing")
    db_test.add(existing)
    db_test.flush()
    db_test.add(ManyToManyLinkModel(owner_id=owner.id, target_id=existing.id))
    db_test.flush()

    target = owner.add_related_item(
        data={"name": "Ignored", "slug": "existing"},
        target_model_class=ManyToManyTargetModel,
        link_model_class=ManyToManyLinkModel,
        self_foreign_key="owner_id",
        target_foreign_key="target_id",
        lookup_fields=["slug"],
    )

    assert target is existing
    assert _link_count(db_test, owner.id, existing.id) == 1


def test_remove_related_item_deletes_existing_link(db_test):
    owner = _create_owner(db_test)
    target = ManyToManyTargetModel(name="Target A", slug="target-a")
    db_test.add(target)
    db_test.flush()
    db_test.add(ManyToManyLinkModel(owner_id=owner.id, target_id=target.id))
    db_test.flush()

    removed = owner.remove_related_item(
        item_id=target.id,
        link_model_class=ManyToManyLinkModel,
        self_foreign_key="owner_id",
        target_foreign_key="target_id",
    )

    assert removed is True
    assert _link_count(db_test, owner.id, target.id) == 0


def test_remove_related_item_returns_false_when_link_missing(db_test):
    owner = _create_owner(db_test)

    removed = owner.remove_related_item(
        item_id=999,
        link_model_class=ManyToManyLinkModel,
        self_foreign_key="owner_id",
        target_foreign_key="target_id",
    )

    assert removed is False
