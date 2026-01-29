#!/usr/bin/env python3
"""Sample Query Checker - Demonstrates QueryAnalyzer with SampleModel"""
from datetime import date
from repom.diagnostics.query_analyzer import QueryAnalyzer
from repom.database import _db_manager, Base, get_sync_engine
from repom.examples.models.sample import SampleModel

def setup_database():
    """Create database tables if they don't exist."""
    engine = get_sync_engine()
    Base.metadata.create_all(engine)

def run_sample_check():
    print("\n" + "="*70)
    print("SampleModel Query Analysis")
    print("="*70)
    
    analyzer = QueryAnalyzer()
    
    # Test: Basic operations
    print("\n[Test] Basic CRUD Operations")
    print("-" * 70)
    
    with _db_manager.get_sync_session() as session:
        with analyzer.capture(model='SampleModel'):
            # Create samples
            samples = [SampleModel(value=f"Sample {i}") for i in range(3)]
            session.add_all(samples)
            session.flush()
            
            # Query all
            all_samples = session.query(SampleModel).all()
            print(f"  Created {len(all_samples)} samples")
            
            session.commit()
    
    analyzer.print_report()
    print("\n[OK] Analysis complete!")
    print("="*70 + "\n")

if __name__ == '__main__':
    try:
        setup_database()
        run_sample_check()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
