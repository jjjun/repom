"""
Test if we can control migration file location dynamically in env.py
without requiring version_locations in alembic.ini
"""
import os
from pathlib import Path
from alembic.config import Config
from alembic import command


def test_dynamic_version_path():
    """Test if process_revision_directives can control file location"""

    # Create test directory
    test_dir = Path(__file__).parent / "test_output"
    test_dir.mkdir(exist_ok=True)
    versions_dir = test_dir / "versions"
    versions_dir.mkdir(exist_ok=True)

    # Create minimal alembic.ini
    alembic_ini = test_dir / "alembic.ini"
    alembic_ini.write_text("""[alembic]
script_location = alembic
""")

    # Create Config object
    config = Config(str(alembic_ini))

    # Try to use version_path parameter
    print(f"Testing version_path parameter...")
    print(f"Target directory: {versions_dir}")

    # This should work according to the signature we found
    try:
        command.revision(
            config,
            message="test migration",
            autogenerate=False,
            version_path=str(versions_dir)
        )
        print("✅ SUCCESS: version_path parameter works!")

        # Check if file was created in the right location
        files = list(versions_dir.glob("*.py"))
        if files:
            print(f"✅ File created at: {files[0]}")
            return True
        else:
            print("❌ No file created")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


if __name__ == "__main__":
    result = test_dynamic_version_path()
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
