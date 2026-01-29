#!/usr/bin/env python3
"""Sample Query Checker - Demonstrates QueryAnalyzer with any model"""
from sqlalchemy import String, Text
from repom.diagnostics.query_analyzer import QueryAnalyzer, get_model_by_name
from repom.database import _db_manager, Base, get_sync_engine
from repom.utility import load_models


def _get_sample_field(model_class) -> str | None:
    """モデルから適切なサンプルフィールドを自動検出

    Args:
        model_class: SQLAlchemyモデルクラス

    Returns:
        str | None: 検出されたフィールド名、見つからない場合はNone

    検出ロジック:
        1. 優先順位の高いフィールド名（value, name, title等）を探す
        2. なければ最初の文字列型フィールドを使う
        3. id, created_at, updated_at は除外
    """
    # 優先順位の高いフィールド名
    priority_names = ['value', 'name', 'title', 'label', 'text', 'description', 'content']

    columns = model_class.__table__.columns

    # 優先順位の高いフィールド名を探す
    for name in priority_names:
        if name in columns:
            col = columns[name]
            if isinstance(col.type, (String, Text)):
                return name

    # なければ最初の文字列型フィールドを使う
    excluded_names = {'id', 'created_at', 'updated_at', 'deleted_at'}
    for col in columns:
        if col.name not in excluded_names and isinstance(col.type, (String, Text)):
            return col.name

    return None


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

    # モデルから適切なサンプルフィールドを検出
    sample_field = _get_sample_field(model_class)

    # Test: Basic operations
    print("\n[Test] Basic CRUD Operations")
    print("-" * 70)

    with _db_manager.get_sync_session() as session:
        with analyzer.capture(model=model_name):
            if sample_field:
                # Create sample records with detected field
                print(f"  Using field: '{sample_field}' for sample data")
                samples = [model_class(**{sample_field: f"Sample {i}"}) for i in range(3)]
                session.add_all(samples)
                session.flush()
                print(f"  Created {len(samples)} {model_name} records")
            else:
                # No suitable field found - use existing data
                print(f"  [INFO] No suitable text field found, using existing data")

            # Query all
            all_samples = session.query(model_class).all()
            print(f"  Total records in DB: {len(all_samples)}")

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
