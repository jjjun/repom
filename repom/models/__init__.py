"""
Auto-import all models in this directory and subdirectories.
This ensures all SQLAlchemy models are registered with Base.metadata
without needing to manually add imports.
"""
from pathlib import Path
from repom.utility import auto_import_models

# Auto-import all models in this directory
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='repom.models'
)
