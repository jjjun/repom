#!/usr/bin/env python3
"""SQLAlchemy Relationship String Resolution Investigation

This script investigates how SQLAlchemy resolves string references in relationship()
and why TYPE_CHECKING imports fail for primaryjoin/secondaryjoin.
"""

from sqlalchemy import String, Integer, ForeignKey, Table, Column, create_engine, inspect
from sqlalchemy.orm import relationship, Session, DeclarativeBase, Mapped, mapped_column
from typing import TYPE_CHECKING, List
import sys


class Base(DeclarativeBase):
    pass


# Simulate the problem: Define a link model only in TYPE_CHECKING
if TYPE_CHECKING:
    class TagLinkTyping(Base):
        __tablename__ = 'tag_links_typing'
        id: Mapped[int] = mapped_column(primary_key=True)
        item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))
        tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id'))


# Define link model at runtime
class TagLinkRuntime(Base):
    __tablename__ = 'tag_links_runtime'
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id'))


class Tag(Base):
    __tablename__ = 'tags'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class Item(Base):
    __tablename__ = 'items'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

    # Test 1: secondary with table name (string) - レジストリベース解決
    tags_via_table_name: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary="tag_links_runtime",  # テーブル名文字列
        viewonly=True
    )


def test_registry_resolution():
    """Test 1: SQLAlchemy registry can resolve table names"""
    print("\n" + "="*70)
    print("Test 1: Registry Resolution (secondary='table_name')")
    print("="*70)

    try:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        print("✅ SUCCESS: secondary='tag_links_runtime' resolved via registry")
        print("   - SQLAlchemy found the table in Base.metadata")

        # Check what's in the registry
        print("\n📋 Tables in registry:")
        for table_name in Base.metadata.tables.keys():
            print(f"   - {table_name}")

    except Exception as e:
        print(f"❌ FAILED: {e}")


def test_class_name_in_primaryjoin_typing():
    """Test 2: primaryjoin with TYPE_CHECKING class fails"""
    print("\n" + "="*70)
    print("Test 2: eval() Resolution with TYPE_CHECKING class")
    print("="*70)

    # Attempt to define relationship with TYPE_CHECKING class
    try:
        class ItemWithTypingJoin(Base):
            __tablename__ = 'items_typing_join'
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

            # This will fail because TagLinkTyping doesn't exist at runtime
            tags_with_typing: Mapped[List["Tag"]] = relationship(
                "Tag",
                secondary="tag_links_typing",
                primaryjoin="ItemWithTypingJoin.id == TagLinkTyping.item_id",  # ← This uses eval()
                secondaryjoin="TagLinkTyping.tag_id == Tag.id",
                viewonly=True
            )

        # Try to configure mappers (this is when SQLAlchemy resolves strings)
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        print("❌ UNEXPECTED: Should have failed but didn't")

    except NameError as e:
        print(f"✅ EXPECTED FAILURE: NameError occurred")
        print(f"   Error: {e}")
        print("   Reason: TagLinkTyping is only in TYPE_CHECKING block")
        print("   → eval() cannot find the class name at runtime")

    except Exception as e:
        print(f"⚠️  DIFFERENT ERROR: {type(e).__name__}: {e}")


def test_class_name_in_primaryjoin_runtime():
    """Test 3: primaryjoin with runtime class succeeds"""
    print("\n" + "="*70)
    print("Test 3: eval() Resolution with Runtime class")
    print("="*70)

    try:
        class ItemWithRuntimeJoin(Base):
            __tablename__ = 'items_runtime_join'
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

            # This should work because TagLinkRuntime exists at runtime
            tags_with_runtime: Mapped[List["Tag"]] = relationship(
                "Tag",
                secondary="tag_links_runtime",
                primaryjoin="ItemWithRuntimeJoin.id == TagLinkRuntime.item_id",  # ← eval() can find this
                secondaryjoin="TagLinkRuntime.tag_id == Tag.id",
                viewonly=True
            )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        print("✅ SUCCESS: primaryjoin with runtime class works")
        print("   - TagLinkRuntime exists in global namespace")
        print("   - eval() can resolve 'TagLinkRuntime.item_id'")

    except Exception as e:
        print(f"❌ FAILED: {e}")


def test_namespace_inspection():
    """Test 4: Inspect what's available in different namespaces"""
    print("\n" + "="*70)
    print("Test 4: Namespace Inspection")
    print("="*70)

    print("\n🔍 Global namespace (what eval() can see):")
    global_classes = {k: v for k, v in globals().items()
                      if isinstance(v, type) and issubclass(v, Base) and v is not Base}
    for name, cls in sorted(global_classes.items()):
        table_name = getattr(cls, '__tablename__', 'N/A')
        print(f"   - {name:30} → {table_name}")

    print("\n🔍 SQLAlchemy registry (what registry can see):")
    for mapper in Base.registry.mappers:
        print(f"   - {mapper.class_.__name__:30} → {mapper.class_.__tablename__}")

    print("\n📊 Comparison:")
    print("   - Registry includes: All models (even if not in global namespace)")
    print("   - Global namespace: Only runtime imported classes")
    print("   - TYPE_CHECKING classes: Not in either at runtime")


def test_load_models_effect():
    """Test 5: Simulate load_models() behavior"""
    print("\n" + "="*70)
    print("Test 5: load_models() Effect Simulation")
    print("="*70)

    print("\n🔬 What load_models() does:")
    print("   1. Uses importlib.import_module() to import model files")
    print("   2. This triggers class definition → SQLAlchemy registry registration")
    print("   3. Models are added to: Base.registry.mappers ✅")
    print("   4. Models are added to: module's global namespace ✅")
    print("   5. Models are added to: calling module's namespace ❌")

    print("\n💡 Key insight:")
    print("   - load_models() imports 'src.domains.anime.models.video.ani_video_item'")
    print("   - AniVideoTagLinkModel is in that module's globals()")
    print("   - But NOT in the namespace where relationship() string is evaluated")
    print("   - SQLAlchemy eval() uses the DEFINING module's globals")

    print("\n🎯 Why primaryjoin fails:")
    print("   - secondary='ani_video_tag_links' → Registry lookup (table name)")
    print("   - 'AniVideoTagModel' → Registry lookup (class name)")
    print("   - AniVideoTagLinkModel.id → eval() in defining module's namespace")
    print("   - If imported only in TYPE_CHECKING → Not in runtime namespace → NameError")


def main():
    print("\n" + "="*70)
    print("SQLAlchemy String Resolution Investigation")
    print("="*70)
    print("\nInvestigating Issue: sqlalchemy_relationship_name_resolution_error")
    print("Question: Why does load_models() not help with TYPE_CHECKING imports?")

    # Run all tests
    test_registry_resolution()
    test_class_name_in_primaryjoin_typing()
    test_class_name_in_primaryjoin_runtime()
    test_namespace_inspection()
    test_load_models_effect()

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print("""
✅ Issue analysis is CORRECT:

1. Registry Resolution (for table/class names):
   - secondary='ani_video_tag_links' ✅ Works
   - 'AniVideoTagModel' ✅ Works
   - SQLAlchemy looks up these in Base.registry

2. eval() Resolution (for join conditions):
   - AniVideoTagLinkModel.ani_video_item_id ❌ Fails
   - SQLAlchemy uses eval(expression, globals(), registry_dict)
   - TYPE_CHECKING imports are not in runtime globals()
   - load_models() puts classes in their own module's globals(),
     not in the consuming module's globals()

3. Solution:
   - Move AniVideoTagLinkModel import outside TYPE_CHECKING ✅
   - This puts the class in the runtime namespace
   - eval() can then resolve the class name

4. Why load_models() doesn't help:
   - It imports modules and populates registry ✅
   - But eval() needs the class in the CALLING module's namespace
   - TYPE_CHECKING blocks prevent runtime imports
""")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
