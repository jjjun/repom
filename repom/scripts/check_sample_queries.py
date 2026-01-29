#!/usr/bin/env python3
"""Sample Query Checker - Demonstrates QueryAnalyzer with any model"""
from repom.diagnostics.query_analyzer import QueryAnalyzer, get_model_by_name
from repom.database import _db_manager, Base, get_sync_engine
from repom.utility import load_models


def run_sample_check(model_name: str = 'SampleModel'):
    """Run query analysis on specified model.

    Args:
        model_name: Name of the model to analyze (e.g., 'SampleModel', 'User')
    """
    # Load models from configured locations first
    load_models(context="check_sample_queries")

    # Create database tables after models are loaded
    engine = get_sync_engine()
    Base.metadata.create_all(engine)

    print("\n" + "="*70)
    print(f"{model_name} Query Analysis")
    print("="*70)

    # Get model class dynamically
    model_class = get_model_by_name(model_name)
    if model_class is None:
        print(f"\n[ERROR] Model '{model_name}' not found.")
        print("Available models:")
        from repom.diagnostics.query_analyzer import list_all_models
        for name in list_all_models():
            print(f"  - {name}")
        return

    analyzer = QueryAnalyzer()

    # Test: Basic operations
    print("\n[Test] Basic CRUD Operations")
    print("-" * 70)

    with _db_manager.get_sync_session() as session:
        with analyzer.capture(model=model_name):
            # Create sample records
            samples = [model_class(value=f"Sample {i}") for i in range(3)]
            session.add_all(samples)
            session.flush()

            # Query all
            all_samples = session.query(model_class).all()
            print(f"  Created {len(all_samples)} {model_name} records")

            session.commit()

    analyzer.print_report()
    print("\n[OK] Analysis complete!")
    print("="*70 + "\n")


if __name__ == '__main__':
    try:
        run_sample_check(model_name='SampleModel')  # デフォルトは SampleModel
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
