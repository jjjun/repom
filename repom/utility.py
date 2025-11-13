import os
import inflect
import unicodedata
import importlib
from pathlib import Path
from typing import Optional, Set

"""
inflect
英語の単語の複数形、単数形、序数、冠詞などを生成するためのPythonライブラリです。
このライブラリを使用すると、英語の文法規則に基づいて単語の形態を変化させることができます。
主な機能
複数形の生成: 単語の複数形を生成します。
単数形の生成: 単語の単数形を生成します。
序数の生成: 数字を序数(1st, 2nd, 3rd など)に変換します。
冠詞の追加: 単語に適切な冠詞(a, an, the)を追加します。
"""

# Default directories to exclude from auto-import
DEFAULT_EXCLUDED_DIRS = {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}


def get_plural_tablename(file_path: str) -> str:
    """
    ファイル名から拡張子を除去し、複数形に変換してテーブル名を取得する関数。

    Args:
        file_path (str): ファイルのパス

    Returns:
        str: 複数形に変換されたテーブル名
    """
    # ファイル名を取得し、拡張子を除去
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    # inflect エンジンを初期化
    p = inflect.engine()

    # ファイル名を複数形に変換
    table_name = p.plural(file_name)

    return table_name


def normalize_text(s: str) -> str:
    """
    テキストの正規化（全角・半角・空白・小文字化）
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(" ", "").replace("　", "")
    return s.lower()


def auto_import_models(
    models_dir: str | Path,
    base_package: str,
    excluded_dirs: Optional[Set[str]] = None
) -> None:
    """
    Recursively import all Python modules in models directory, excluding utility directories.

    This function automatically discovers and imports all model files in a directory structure,
    making them available to SQLAlchemy's metadata without manual imports.

    Args:
        models_dir: Path to the models directory (can be string or Path object)
        base_package: Base package name (e.g., 'myapp.models')
        excluded_dirs: Set of directory names to exclude. Defaults to DEFAULT_EXCLUDED_DIRS
                      {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}

    Example:
        # In your models/__init__.py
        from pathlib import Path
        from repom.utility import auto_import_models

        auto_import_models(
            models_dir=Path(__file__).parent,
            base_package='myapp.models'
        )

        # With custom exclusions
        auto_import_models(
            models_dir=Path(__file__).parent,
            base_package='myapp.models',
            excluded_dirs={'base', 'mixin', 'tests'}
        )

    Directory Structure Example:
        myapp/models/
        ├── __init__.py          # Call auto_import_models here
        ├── user.py              # ✅ Imported
        ├── product.py           # ✅ Imported
        ├── base/                # ❌ Excluded
        │   └── helper.py
        └── admin/
            └── user.py          # ✅ Imported as myapp.models.admin.user

    Features:
        - Recursively scans all subdirectories
        - Skips utility directories (base, mixin, validators, etc.)
        - Skips files starting with underscore (__init__.py, _private.py)
        - Sorts files alphabetically for consistent import order
        - Handles import errors gracefully with warnings
        - Uses Python's import cache (no duplicate imports)
    """
    if excluded_dirs is None:
        excluded_dirs = DEFAULT_EXCLUDED_DIRS

    models_dir = Path(models_dir)

    # Collect all Python files to import
    py_files = []
    for py_file in models_dir.rglob('*.py'):
        # Skip __pycache__ directories
        if '__pycache__' in py_file.parts:
            continue

        # Skip files starting with underscore (like __init__.py)
        if py_file.stem.startswith('_'):
            continue

        # Skip excluded directories
        relative_path = py_file.relative_to(models_dir)
        if any(excluded_dir in relative_path.parts for excluded_dir in excluded_dirs):
            continue

        py_files.append((py_file, relative_path))

    # Sort files alphabetically to ensure consistent import order
    py_files.sort(key=lambda x: str(x[1]))

    # Import all collected files
    for py_file, relative_path in py_files:
        # Convert file path to module path (e.g., admin/user.py -> admin.user)
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        module_name = '.'.join(module_parts)

        # Import the module
        full_module_name = f'{base_package}.{module_name}' if module_name else base_package
        try:
            importlib.import_module(full_module_name)
        except Exception as e:
            # Log import errors but don't fail completely
            print(f"Warning: Failed to import {full_module_name}: {e}")
