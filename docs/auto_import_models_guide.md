# Auto Import Models - Usage Guide

## Overview

The `auto_import_models` utility function automatically discovers and imports all model files in your models directory, eliminating the need to manually maintain imports in `__init__.py`.

## Basic Usage

### In Your Project's `models/__init__.py`

```python
from pathlib import Path
from repom.utility import auto_import_models

# Auto-import all models in this directory
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models'  # Replace with your package name
)
```

That's it! No need to manually add imports when you create new models.

## How It Works

1. **Scans Directory**: Recursively scans the models directory
2. **Filters Files**: Skips utility directories and private files
3. **Sorts Alphabetically**: Ensures consistent import order
4. **Imports Modules**: Loads each model file
5. **Uses Cache**: Python's import cache prevents duplicate loads

## Directory Structure

### Example Project Structure

```
your_project/
└── models/
    ├── __init__.py           # Call auto_import_models here
    ├── user.py               # ✅ Imported
    ├── product.py            # ✅ Imported
    ├── base/                 # ❌ Excluded (utility directory)
    │   ├── helper.py
    │   └── mixins.py
    ├── validators/           # ❌ Excluded (utility directory)
    │   └── email.py
    └── admin/                # ✅ Subdirectory models imported
        ├── user.py           # ✅ Imported as your_project.models.admin.user
        └── settings.py       # ✅ Imported as your_project.models.admin.settings
```

### Default Excluded Directories

The following directories are automatically excluded:
- `base/` - Base classes and helpers
- `mixin/` - Mixin classes
- `validators/` - Validation utilities
- `utils/` - Utility functions
- `helpers/` - Helper functions
- `__pycache__/` - Python cache

## Advanced Usage

### Custom Exclusions

```python
from pathlib import Path
from repom.utility import auto_import_models

# Exclude additional directories
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'base', 'mixin', 'validators', 'tests', 'fixtures'}
)
```

### Minimal Exclusions

```python
from pathlib import Path
from repom.utility import auto_import_models

# Only exclude __pycache__
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'__pycache__'}
)
```

## Model Dependencies

If Model A depends on Model B, you have two options:

### Option 1: File Naming (Recommended)

```
models/
├── 01_user.py      # Imported first
└── 02_profile.py   # Imported second (depends on user)
```

### Option 2: Explicit Import in Model File

```python
# models/profile.py
from your_project.models.user import User  # Explicit dependency

class Profile(BaseModel):
    __tablename__ = 'profiles'
    user_id = Column(Integer, ForeignKey(User.id))
```

## Benefits

✅ **No Manual Maintenance**: Add models without updating `__init__.py`  
✅ **Consistent Import Order**: Alphabetically sorted for predictability  
✅ **Subdirectory Support**: Organize models in nested folders  
✅ **Utility Exclusion**: Keep helper code separate from models  
✅ **Error Handling**: Graceful warnings for import failures  
✅ **Performance**: Uses Python's import cache (no duplicates)

## Integration with Alembic

When using with Alembic migrations, ensure your `alembic/env.py` calls the model loading hook:

```python
from your_project.config import load_set_model_hook_function

# This will trigger auto_import_models
load_set_model_hook_function()
```

## Troubleshooting

### Models Not Detected

1. Check that files don't start with `_` (underscore)
2. Verify files are not in excluded directories
3. Ensure files have `.py` extension
4. Check for import errors in model files

### Import Errors

If you see warnings like:
```
Warning: Failed to import your_project.models.example: <error>
```

Check the specific model file for syntax or dependency errors.

## Example: Real Project

```python
# your_project/models/__init__.py
"""
Auto-import all models for SQLAlchemy metadata registration.
"""
from pathlib import Path
from repom.utility import auto_import_models

# Import all models except utilities and tests
auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='your_project.models',
    excluded_dirs={'base', 'mixin', 'validators', 'tests', '__pycache__'}
)

# Optionally export specific models for convenience
from your_project.models.user import User
from your_project.models.product import Product

__all__ = ['User', 'Product']
```

## See Also

- `repom/models/__init__.py` - Reference implementation
- `repom/utility.py` - Function source code
- `docs/issue/sqlalchemy_column_inheritance_constraint.md` - Related documentation
