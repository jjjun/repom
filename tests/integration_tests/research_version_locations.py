"""
Research: Can we control migration file location programmatically in env.py?

Based on Alembic source code investigation:
1. ScriptDirectory.__init__() accepts version_locations parameter
2. alembic.command.revision() accepts version_path parameter
3. Config.set_main_option() can set version_locations dynamically

Goal: Make file creation and execution use the same location source (RepomConfig)
"""
import os
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_approach_1_set_main_option():
    """
    Approach 1: Use config.set_main_option() before creating ScriptDirectory

    Question: Does this affect alembic revision command?
    Answer: Testing...
    """
    print("=" * 70)
    print("Approach 1: config.set_main_option('version_locations', ...)")
    print("=" * 70)

    # This is what we currently do in env.py (commit 70003dc)
    config = Config("alembic.ini")
    test_path = str(Path(__file__).parent / "test_output" / "approach1")

    config.set_main_option("version_locations", test_path)

    # Check if ScriptDirectory picks it up
    script_location = config.get_main_option("script_location")
    script = ScriptDirectory.from_config(config)

    print(f"Script location: {script_location}")
    print(f"Version locations: {script.version_locations}")
    print(f"Does it use our path? {test_path in script.version_locations}")
    print()


def test_approach_2_script_directory_constructor():
    """
    Approach 2: Pass version_locations directly to ScriptDirectory constructor

    Question: Can we override ScriptDirectory creation in env.py?
    Answer: Maybe through process_revision_directives?
    """
    print("=" * 70)
    print("Approach 2: ScriptDirectory(version_locations=[...])")
    print("=" * 70)

    test_path = str(Path(__file__).parent / "test_output" / "approach2")
    Path(test_path).mkdir(parents=True, exist_ok=True)

    script = ScriptDirectory(
        dir="alembic",
        version_locations=[test_path]
    )

    print(f"Version locations: {script.version_locations}")
    print(f"Does it use our path? {test_path in script.version_locations}")
    print()


def test_approach_3_alembic_ini_comment():
    """
    Approach 3: Current solution - require version_locations in alembic.ini

    This is what we discovered works, but it requires external projects
    to maintain their own alembic.ini with version_locations line.
    """
    print("=" * 70)
    print("Approach 3: version_locations in alembic.ini (Current Solution)")
    print("=" * 70)

    print("Pros:")
    print("  ✅ Works reliably for both file creation and execution")
    print("  ✅ Standard Alembic approach")
    print()
    print("Cons:")
    print("  ❌ External projects need custom alembic.ini (not minimal)")
    print("  ❌ Duplicates path configuration (alembic.ini + RepomConfig)")
    print("  ❌ Confusing: file creation uses .ini, execution uses env.py")
    print()


if __name__ == "__main__":
    print("\n")
    print("RESEARCH: Dynamic version_locations Control")
    print("=" * 70)
    print()

    try:
        test_approach_1_set_main_option()
    except Exception as e:
        print(f"❌ Approach 1 failed: {e}\n")

    try:
        test_approach_2_script_directory_constructor()
    except Exception as e:
        print(f"❌ Approach 2 failed: {e}\n")

    test_approach_3_alembic_ini_comment()

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("Testing if set_main_option() actually affects 'alembic revision'...")
