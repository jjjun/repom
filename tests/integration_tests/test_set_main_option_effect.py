"""
Direct test: Does config.set_main_option('version_locations') affect 'alembic revision'?

This simulates what happens in our env.py (commit 70003dc)
"""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_set_main_option_affects_script_directory():
    project_root = Path(__file__).parent.parent.parent
    alembic_ini = project_root / "alembic.ini"
    config = Config(str(alembic_ini))
    custom_path = str(project_root / "tests" / "integration_tests" / "custom_versions")

    config.set_main_option("version_locations", custom_path)

    script = ScriptDirectory.from_config(config)
    assert custom_path in script.version_locations
