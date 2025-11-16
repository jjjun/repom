"""
Direct test: Does config.set_main_option('version_locations') affect 'alembic revision'?

This simulates what happens in our env.py (commit 70003dc)
"""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

# Use actual alembic.ini from project root
project_root = Path(__file__).parent.parent.parent
alembic_ini = project_root / "alembic.ini"

print(f"Using alembic.ini: {alembic_ini}")
print()

# Create Config
config = Config(str(alembic_ini))

# Check original version_locations
script = ScriptDirectory.from_config(config)
print("BEFORE set_main_option:")
print(f"  version_locations from ini: {config.get_main_option('version_locations')}")
print(f"  ScriptDirectory.version_locations: {script.version_locations}")
print()

# Set custom version_locations (what env.py does)
custom_path = str(project_root / "tests" / "integration_tests" / "custom_versions")
config.set_main_option("version_locations", custom_path)

# Create NEW ScriptDirectory AFTER set_main_option
script_after = ScriptDirectory.from_config(config)
print("AFTER set_main_option:")
print(f"  version_locations from ini: {config.get_main_option('version_locations')}")
print(f"  ScriptDirectory.version_locations: {script_after.version_locations}")
print()

# Check if it picked up the new path
if custom_path in script_after.version_locations:
    print("✅ SUCCESS: set_main_option() DOES affect ScriptDirectory!")
    print(f"   Custom path is in version_locations: {custom_path}")
else:
    print("❌ FAILED: set_main_option() does NOT affect ScriptDirectory")
    print(f"   Expected: {custom_path}")
    print(f"   Actual: {script_after.version_locations}")
