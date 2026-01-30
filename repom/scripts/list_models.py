#!/usr/bin/env python3
"""List Models - Display all models loaded by load_models()"""

from repom.utility import load_models
from repom.models.base_model import Base


def list_models():
    """Display all models loaded by load_models()."""
    # Load models from configured locations
    load_models(context="list_models")

    print("\n" + "="*70)
    print("Loaded Models")
    print("="*70)

    if not Base.registry.mappers:
        print("\n[INFO] No models loaded.")
        print("="*70 + "\n")
        return

    # Collect model information
    models_info = []
    for mapper in Base.registry.mappers:
        model_class = mapper.class_
        table = model_class.__table__

        info = {
            'name': model_class.__name__,
            'table': table.name,
            'pk': ', '.join([col.name for col in table.primary_key]),
            'columns': len(table.columns)
        }
        models_info.append(info)

    # Sort by model name
    models_info.sort(key=lambda x: x['name'])

    # Display
    print(f"\nTotal: {len(models_info)} models\n")

    max_name = max(len(info['name']) for info in models_info)
    max_table = max(len(info['table']) for info in models_info)

    for info in models_info:
        print(f"  {info['name']:<{max_name}}  →  {info['table']:<{max_table}}  ({info['columns']} cols)")

    print("="*70 + "\n")


if __name__ == '__main__':
    list_models()
