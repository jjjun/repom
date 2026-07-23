"""Verify that the mock consumer's Alembic paths are checkout-independent."""

from pathlib import Path

from alembic.config import Config


fixture_root = Path(__file__).resolve().parent
repository_root = fixture_root.parents[2]
config = Config(str(fixture_root / "alembic.ini"))

expected_script = (repository_root / "alembic").resolve()
expected_versions = (fixture_root / "alembic" / "versions").resolve()
actual_script = Path(config.get_main_option("script_location")).resolve()
actual_versions = Path(config.get_main_option("version_locations")).resolve()

print(f"script_location: {actual_script}")
print(f"version_locations: {actual_versions}")

if actual_script != expected_script:
    raise SystemExit(
        f"unexpected script_location: {actual_script} != {expected_script}"
    )
if actual_versions != expected_versions:
    raise SystemExit(
        f"unexpected version_locations: {actual_versions} != {expected_versions}"
    )

print("Alembic paths are portable and resolve to the expected directories.")
