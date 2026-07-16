"""Test Alembic's version_path parameter with configured version_locations."""
from pathlib import Path
from alembic.config import Config
from alembic import command


def _run_version_path_test(test_dir: Path):
    """Run a revision using version_path and configured version_locations."""

    # Create test directory
    test_dir.mkdir(exist_ok=True)
    versions_dir = test_dir / "versions"
    versions_dir.mkdir(exist_ok=True)

    # Create minimal alembic.ini
    alembic_ini = test_dir / "alembic.ini"
    alembic_ini.write_text("""[alembic]
script_location = alembic
path_separator = os
version_locations = %(here)s/versions
""")

    # Create Config object
    config = Config(str(alembic_ini))

    # Try to use version_path parameter
    print("Testing version_path parameter...")
    print(f"Target directory: {versions_dir}")

    # This should work according to the signature we found
    command.revision(
        config,
        message="test migration",
        autogenerate=False,
        version_path=str(versions_dir)
    )
    print("[OK] SUCCESS: version_path parameter works!")

    # Check if file was created in the right location
    files = list(versions_dir.glob("*.py"))
    assert files
    print(f"[OK] File created at: {files[0]}")


def test_version_path_writes_to_configured_version_location(tmp_path):
    _run_version_path_test(tmp_path)


if __name__ == "__main__":
    _run_version_path_test(Path(__file__).parent / "test_output")
    print("\nResult: SUCCESS")
