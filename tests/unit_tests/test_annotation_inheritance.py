"""Tests for annotation inheritance and BaseModel subclass behavior."""

from tests._init import *

from datetime import datetime
from typing import get_type_hints

from sqlalchemy import String, inspect
from sqlalchemy.orm import Mapped, mapped_column

from repom.custom_types.AutoDateTime import AutoDateTime
from repom.models.base_model import BaseModel


class AnnotationBaseModel(BaseModel):
    """Abstract base with an annotation that should not leak into child __annotations__."""

    __abstract__ = True
    shared_text: Mapped[str]


class AnnotationLeafModel(AnnotationBaseModel):
    """Concrete subclass without local annotations."""

    __tablename__ = "annotation_leaf_models"


class TimestampMixin:
    """Mixin that contributes mapped columns via annotations."""

    created_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)


class MixinUseIdFalseModel(TimestampMixin, BaseModel, use_id=False):
    """Model that combines mixin annotations with BaseModel(use_id=False)."""

    __tablename__ = "mixin_use_id_false_models"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class LabelMixin:
    """Simple mixin used to validate multiple inheritance with BaseModel flags."""

    label: Mapped[str] = mapped_column(String(100), nullable=False)


class MultiInheritanceFlagModel(LabelMixin, BaseModel, use_id=False, use_created_at=True):
    """Model that mixes custom columns with BaseModel flags."""

    __tablename__ = "multi_inheritance_flag_models"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)


class ExistingBehaviorNoIdModel(BaseModel, use_id=False):
    """Control model to guard existing no-id behavior."""

    __tablename__ = "existing_behavior_no_id_models"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


def test_class_annotations_are_not_leaked_from_base_when_no_local_annotations():
    """Child class should not keep parent-only annotation in its own __annotations__."""
    own_annotations = AnnotationLeafModel.__dict__.get("__annotations__", {})
    assert "shared_text" not in own_annotations
    assert "id" in own_annotations

    # MRO-aware hints still include inherited annotations.
    hints = get_type_hints(AnnotationLeafModel)
    assert "shared_text" in hints


def test_mixin_mapped_annotations_remain_visible_with_use_id_false():
    """Mapped column from mixin should remain usable with use_id=False."""
    mapper = inspect(MixinUseIdFalseModel)
    column_names = [col.key for col in mapper.columns]

    assert "created_at" in column_names
    assert "id" not in column_names

    # get_type_hints merges MRO annotations; created_at should remain visible.
    hints = get_type_hints(MixinUseIdFalseModel)
    assert "created_at" in hints


def test_multiple_inheritance_with_use_flags_does_not_add_unexpected_id():
    """Multiple inheritance with BaseModel flags should not add id when use_id=False."""
    mapper = inspect(MultiInheritanceFlagModel)
    column_names = [col.key for col in mapper.columns]

    assert "id" not in column_names
    assert "created_at" in column_names
    assert "label" in column_names
    assert "code" in column_names


def test_existing_behavior_use_id_false_still_works_with_new_annotation_tests():
    """Existing behavior guard: use_id=False keeps custom primary key and no id."""
    mapper = inspect(ExistingBehaviorNoIdModel)
    column_names = [col.key for col in mapper.columns]
    primary_keys = [col.key for col in mapper.primary_key]

    assert "id" not in column_names
    assert "code" in primary_keys

    instance = ExistingBehaviorNoIdModel(code="A-001", name="Alpha")
    data = instance.to_dict()
    assert "id" not in data
    assert data["code"] == "A-001"
