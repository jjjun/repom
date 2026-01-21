"""Test script to reproduce the migration file location issue.

This script simulates the exact scenario from mine-py:
1. CONFIG_HOOK sets custom alembic_versions_path
2. Run `alembic revision --autogenerate`
3. Check where the migration file is actually created

Expected: mock_external_project/alembic/versions/
Actual (bug): repom/alembic/versions/
"""
from repom.config import config
import os
import sys
from pathlib import Path

# Add mock_app to Python path
mock_project_root = Path(__file__).parent
sys.path.insert(0, str(mock_project_root / 'src'))

# Set environment variables BEFORE importing repom
os.environ['CONFIG_HOOK'] = 'mock_app.config:hook_config'
os.environ['EXEC_ENV'] = 'test'

# Now import repom config

print("=" * 80)
print("🔍 Debugging Alembic Version Locations")
print("=" * 80)
print()

print("📍 Mock Project Root:")
print(f"   {mock_project_root}")
print()

print("📍 Expected migration file location (mock_external_project/alembic/versions/):")
expected_path = mock_project_root / 'alembic' / 'versions'
print(f"   {expected_path}")
print()

print("📍 CONFIG_HOOK result:")
print(f"   config.alembic_versions_path = {config.alembic_versions_path}")
print()

print("✅ CONFIG_HOOK is working correctly" if str(expected_path) == config.alembic_versions_path else "❌ CONFIG_HOOK failed")
print()

print("=" * 80)
print("📝 Next Steps:")
print("=" * 80)
print()
print("1. Run from mock_external_project directory:")
print("   cd tests/integration_tests/mock_external_project")
print()
print("2. Set environment variables:")
print("   $env:CONFIG_HOOK='mock_app.config:hook_config'")
print("   $env:EXEC_ENV='test'")
print()
print("3. Add mock_app to PYTHONPATH:")
print("   $env:PYTHONPATH='src;' + $env:PYTHONPATH")
print()
print("4. Run alembic revision command:")
print("   poetry run alembic revision --autogenerate -m 'test migration'")
print()
print("5. Check which directory contains the new migration file:")
print("   - ✅ Expected: mock_external_project/alembic/versions/")
print("   - ❌ Bug: repom/alembic/versions/")
print()

# List current migration files in both locations
print("=" * 80)
print("📂 Current migration files:")
print("=" * 80)
print()

repom_versions = Path(__file__).parent.parent.parent.parent / 'alembic' / 'versions'
mock_versions = expected_path

print(f"repom/alembic/versions/:")
if repom_versions.exists():
    repom_files = [f.name for f in repom_versions.glob('*.py') if f.name != '__init__.py']
    if repom_files:
        for f in repom_files:
            print(f"  - {f}")
    else:
        print("  (empty - correct)")
else:
    print("  (directory does not exist)")
print()

print(f"mock_external_project/alembic/versions/:")
if mock_versions.exists():
    mock_files = [f.name for f in mock_versions.glob('*.py') if f.name != '__init__.py']
    if mock_files:
        for f in mock_files:
            print(f"  - {f}")
    else:
        print("  (empty)")
else:
    print("  (directory does not exist)")
