#!/usr/bin/env python3
"""List Models - Display all models loaded by load_models()"""

import sys
from typing import List

from basekit.discovery import DiscoveryFailure

from repom.utility import ModelInfo, describe_loaded_models


def _display(models: List[ModelInfo], failures: List[DiscoveryFailure]) -> None:
    """Print the model list and, if any, the import-failures section."""
    print("\n" + "="*70)
    print("Loaded Models")
    print("="*70)

    if not models:
        print("\n[INFO] No models loaded.")
    else:
        print(f"\nTotal: {len(models)} models\n")

        max_name = max(len(model.name) for model in models)
        max_table = max(len(model.table_name) for model in models)

        for model in models:
            print(f"  {model.name:<{max_name}}  →  {model.table_name:<{max_table}}  ({model.column_count} cols)")

    print("="*70 + "\n")

    if failures:
        failure_count = len(failures)
        print(f"[Model Import Failures] ({failure_count} failure{'s' if failure_count != 1 else ''})")
        for idx, failure in enumerate(failures, 1):
            print(f"  {idx}. {failure.target}")
            print(f"     - Type    : {failure.exception_type}")
            print(f"     - Message : {failure.message}")
        print()


def list_models():
    """Display all models loaded by load_models()."""
    models, failures = describe_loaded_models()
    _display(models, failures)


def main():
    """Console entry point for the list_models script.

    Returns:
        0 on success, 1 if any model module failed to import.
    """
    models, failures = describe_loaded_models()
    _display(models, failures)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
