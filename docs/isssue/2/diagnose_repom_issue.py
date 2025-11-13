#!/usr/bin/env python3
"""
SQLAlchemy Relationship Resolution Issue - 診断スクリプト
repom パッケージの問題調査用

このスクリプトを repom リポジトリで実行して問題を再現・診断してください。
"""

def test_individual_imports():
    """モデル単体のインポートテスト（これは成功するはず）"""
    print("=== 1. Individual Model Import Test ===")
    try:
        # 実際のモデルクラスに置き換えてください
        from your_models.model_a import ModelA
        from your_models.model_b import ModelB
        
        print("✓ ModelA import: SUCCESS")
        print("✓ ModelB import: SUCCESS")
        print(f"  ModelA table: {ModelA.__tablename__}")
        print(f"  ModelB table: {ModelB.__tablename__}")
        
        return True
    except Exception as e:
        print(f"✗ Model import failed: {e}")
        return False

def test_registry_state():
    """SQLAlchemy レジストリの状態確認"""
    print("\n=== 2. SQLAlchemy Registry State Test ===")
    try:
        from your_models.model_a import ModelA
        
        registry = ModelA.registry
        registry_keys = list(registry._class_registry.data.keys())
        
        print(f"Registry object: {registry}")
        print(f"Total classes in registry: {len(registry_keys)}")
        print(f"Registry keys: {registry_keys}")
        
        # 問題のクラスがレジストリにあるか確認
        target_class = "ModelB"  # 実際の問題クラス名に変更
        if target_class in registry_keys:
            print(f"✓ {target_class} found in registry")
        else:
            print(f"✗ {target_class} NOT found in registry")
            print(f"  This is likely the cause of the relationship resolution error")
        
        return registry_keys
    except Exception as e:
        print(f"✗ Registry check failed: {e}")
        return []

def test_get_response_schema():
    """get_response_schema() メソッドのテスト（これでエラーが発生する）"""
    print("\n=== 3. get_response_schema() Test ===")
    try:
        from your_models.model_a import ModelA  # 実際のモデルに置き換え
        
        print("Calling get_response_schema()...")
        response_schema = ModelA.get_response_schema()
        print("✓ get_response_schema(): SUCCESS")
        print(f"  Schema type: {type(response_schema)}")
        
        return True
    except Exception as e:
        print(f"✗ get_response_schema() failed: {e}")
        print(f"  Error type: {type(e).__name__}")
        
        # SQLAlchemy relationship エラーかチェック
        error_str = str(e)
        if "failed to locate a name" in error_str:
            print("  → This is the SQLAlchemy relationship resolution error!")
            print("  → The issue is in repom's get_response_schema() method")
        
        import traceback
        traceback.print_exc()
        return False

def test_sqlalchemy_mapper_initialization():
    """SQLAlchemy マッパー初期化の詳細テスト"""
    print("\n=== 4. SQLAlchemy Mapper Initialization Test ===")
    try:
        from sqlalchemy import inspect
        from sqlalchemy.orm import configure_mappers
        from your_models.model_a import ModelA
        
        print("Testing mapper access...")
        
        # これが問題を引き起こす可能性がある部分
        mapper = inspect(ModelA)
        print(f"✓ Mapper object: {mapper}")
        
        # column_attrs アクセス（repom の該当箇所）
        print("Accessing column_attrs (this may trigger the error)...")
        column_attrs = mapper.column_attrs
        print(f"✓ Column attrs: {len(list(column_attrs))} columns")
        
        return True
    except Exception as e:
        print(f"✗ Mapper initialization failed: {e}")
        print("  → This is where the relationship resolution error occurs")
        return False

def test_configure_mappers_solution():
    """configure_mappers() による解決テスト"""
    print("\n=== 5. configure_mappers() Solution Test ===")
    try:
        from sqlalchemy.orm import configure_mappers
        
        print("Calling configure_mappers() explicitly...")
        configure_mappers()
        print("✓ configure_mappers(): SUCCESS")
        
        # 再度 get_response_schema() を試す
        print("Retrying get_response_schema() after configure_mappers()...")
        return test_get_response_schema()
        
    except Exception as e:
        print(f"✗ configure_mappers() solution failed: {e}")
        return False

def main():
    """メイン診断実行"""
    print("SQLAlchemy Relationship Resolution Issue - Diagnostic Script")
    print("=" * 60)
    
    # 各テストを順次実行
    results = {}
    
    results['imports'] = test_individual_imports()
    results['registry'] = test_registry_state()
    results['schema'] = test_get_response_schema()
    results['mapper'] = test_sqlalchemy_mapper_initialization()
    results['solution'] = test_configure_mappers_solution()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("=== DIAGNOSTIC SUMMARY ===")
    for test, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"{test:<15}: {status}")
    
    if not results['schema']:
        print("\n🔍 ISSUE CONFIRMED:")
        print("  - get_response_schema() method fails with SQLAlchemy relationship error")
        print("  - This is a repom package issue that needs to be fixed")
        print("  - Check repom/base_model.py around line 188")

if __name__ == "__main__":
    main()