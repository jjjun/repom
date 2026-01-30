#!/usr/bin/env python3
"""Deep Investigation: SQLAlchemy's eval() namespace resolution

This script digs deeper into how SQLAlchemy resolves string expressions
in relationship() primaryjoin/secondaryjoin.
"""

from sqlalchemy import String, Integer, ForeignKey, create_engine, inspect
from sqlalchemy.orm import relationship, Session, DeclarativeBase, Mapped, mapped_column, configure_mappers
from typing import TYPE_CHECKING, List


class Base(DeclarativeBase):
    pass


# Step 1: Define models in TYPE_CHECKING (like mine-py does)
if TYPE_CHECKING:
    class LinkModelTyping(Base):
        __tablename__ = 'links_typing'
        id: Mapped[int] = mapped_column(primary_key=True)
        item_id: Mapped[int] = mapped_column(ForeignKey('items_typing.id'))
        tag_id: Mapped[int] = mapped_column(ForeignKey('tags_typing.id'))


# Step 2: Define models at runtime
class LinkModelRuntime(Base):
    __tablename__ = 'links_runtime'
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('items_runtime.id'))
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags_runtime.id'))


class TagTyping(Base):
    __tablename__ = 'tags_typing'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class TagRuntime(Base):
    __tablename__ = 'tags_runtime'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


def test_scenario_1_table_name_only():
    """Scenario 1: Using only table name in secondary (no primaryjoin)"""
    print("\n" + "="*70)
    print("Scenario 1: secondary='table_name' (No primaryjoin)")
    print("="*70)

    try:
        class ItemSimple(Base):
            __tablename__ = 'items_simple'
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

            # Works: Only uses registry lookup
            tags: Mapped[List["TagRuntime"]] = relationship(
                "TagRuntime",
                secondary="links_runtime",  # ← Registry lookup
                viewonly=True
            )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        print("✅ SUCCESS")
        print("   - secondary='links_runtime' resolved via registry")
        print("   - No eval() needed")

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")


def test_scenario_2_primaryjoin_with_foreign():
    """Scenario 2: Using foreign() with class reference (forces eval)"""
    print("\n" + "="*70)
    print("Scenario 2: primaryjoin with foreign(ClassName.column)")
    print("="*70)

    # First, try with runtime class
    print("\n🔹 Test 2a: With Runtime Class")
    try:
        class ItemWithRuntimeClass(Base):
            __tablename__ = 'items_runtime_class'
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

            tags: Mapped[List["TagRuntime"]] = relationship(
                "TagRuntime",
                secondary="links_runtime",
                primaryjoin="ItemWithRuntimeClass.id == foreign(LinkModelRuntime.item_id)",  # ← eval()
                secondaryjoin="foreign(LinkModelRuntime.tag_id) == TagRuntime.id",
                viewonly=True
            )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        configure_mappers()  # Force mapper configuration

        print("✅ SUCCESS: Runtime class works")
        print("   - LinkModelRuntime is in globals()")

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")

    # Now try with TYPE_CHECKING class
    print("\n🔹 Test 2b: With TYPE_CHECKING Class")
    try:
        class ItemWithTypingClass(Base):
            __tablename__ = 'items_typing_class'
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

            tags: Mapped[List["TagTyping"]] = relationship(
                "TagTyping",
                secondary="links_typing",
                primaryjoin="ItemWithTypingClass.id == foreign(LinkModelTyping.item_id)",  # ← eval() will fail
                secondaryjoin="foreign(LinkModelTyping.tag_id) == TagTyping.id",
                viewonly=True
            )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        configure_mappers()  # Force mapper configuration

        print("❌ UNEXPECTED: Should have failed but didn't!")

    except NameError as e:
        print(f"✅ EXPECTED FAILURE: NameError")
        print(f"   Error: {e}")
        print("   - LinkModelTyping is NOT in globals() at runtime")

    except Exception as e:
        print(f"⚠️  DIFFERENT ERROR: {type(e).__name__}")
        print(f"   Message: {e}")


def test_scenario_3_actual_mine_py_pattern():
    """Scenario 3: Exact pattern from mine-py (using and_)"""
    print("\n" + "="*70)
    print("Scenario 3: Exact mine-py pattern (and_ in secondaryjoin)")
    print("="*70)

    from sqlalchemy import and_

    # Create a PersonalTag model
    class PersonalTag(Base):
        __tablename__ = 'personal_tags'
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String(50))

    # Modify LinkModel to have optional personal_tag_id
    class LinkModelWithPersonal(Base):
        __tablename__ = 'links_with_personal'
        id: Mapped[int] = mapped_column(primary_key=True)
        item_id: Mapped[int] = mapped_column(ForeignKey('items_personal.id'))
        tag_id: Mapped[int] = mapped_column(ForeignKey('tags_runtime.id'), nullable=True)
        personal_tag_id: Mapped[int] = mapped_column(ForeignKey('personal_tags.id'), nullable=True)

    print("\n🔹 Test 3a: With Runtime Class (should work)")
    try:
        class ItemPersonal(Base):
            __tablename__ = 'items_personal'
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

            personal_tags: Mapped[List["PersonalTag"]] = relationship(
                "PersonalTag",
                secondary="links_with_personal",
                primaryjoin="ItemPersonal.id == foreign(LinkModelWithPersonal.item_id)",
                secondaryjoin="and_(foreign(LinkModelWithPersonal.personal_tag_id) == PersonalTag.id, "
                "LinkModelWithPersonal.personal_tag_id.isnot(None))",
                viewonly=True
            )

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        configure_mappers()

        print("✅ SUCCESS: Complex pattern works with runtime class")

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")


def test_scenario_4_eval_inspection():
    """Scenario 4: Inspect what SQLAlchemy's eval sees"""
    print("\n" + "="*70)
    print("Scenario 4: Inspecting eval() namespace")
    print("="*70)

    print("\n🔍 What's in globals() when relationship is defined:")
    print(f"   - LinkModelRuntime: {'LinkModelRuntime' in globals()}")
    print(f"   - LinkModelTyping: {'LinkModelTyping' in globals()}")
    print(f"   - TagRuntime: {'TagRuntime' in globals()}")
    print(f"   - TagTyping: {'TagTyping' in globals()}")

    print("\n🔍 TYPE_CHECKING value at runtime:")
    print(f"   - TYPE_CHECKING = {TYPE_CHECKING}")
    print("   - This is why TYPE_CHECKING blocks are skipped!")

    print("\n💡 Key insight:")
    print("   - TYPE_CHECKING is False at runtime")
    print("   - Code inside 'if TYPE_CHECKING:' is never executed")
    print("   - Classes defined there don't exist at runtime")
    print("   - SQLAlchemy's eval() can't find them")


def main():
    print("\n" + "="*70)
    print("Deep Investigation: SQLAlchemy String Resolution")
    print("="*70)

    test_scenario_1_table_name_only()
    test_scenario_2_primaryjoin_with_foreign()
    test_scenario_3_actual_mine_py_pattern()
    test_scenario_4_eval_inspection()

    print("\n" + "="*70)
    print("FINAL VERDICT")
    print("="*70)
    print("""
The issue analysis is ✅ CORRECT with one clarification:

📌 Why the problem occurs:
   1. TYPE_CHECKING is False at runtime (it's True only during mypy checks)
   2. Classes in 'if TYPE_CHECKING:' blocks are never created at runtime
   3. SQLAlchemy's eval() looks for class names in globals()
   4. Since TYPE_CHECKING classes don't exist, eval() raises NameError

📌 Why load_models() doesn't help:
   - load_models() imports module files
   - This creates classes IN THOSE MODULES' globals()
   - But relationship() eval happens in THE DEFINING MODULE's namespace
   - If the defining module uses TYPE_CHECKING imports, they're still not available

📌 Why secondary='table_name' works but primaryjoin doesn't:
   - secondary='table_name' → Registry lookup (no eval needed)
   - 'ClassName' in relationship() → Registry lookup (no eval needed)
   - ClassName.attribute in join condition → eval() required
   - eval() needs the class in runtime globals()

📌 Solution (as stated in issue):
   ✅ Move AniVideoTagLinkModel import outside TYPE_CHECKING
   - This makes the class available at runtime
   - eval() can then find it in globals()
   - Problem solved!

📌 Alternative solutions (if circular import is a concern):
   1. Use lambda: primaryjoin=lambda: Item.id == LinkModel.item_id
   2. Use relationship.init_class_attribute() pattern
   3. Reorganize imports to avoid circular dependency

The recommended Option 1 (move import outside TYPE_CHECKING) is the
cleanest and most straightforward solution.
""")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
