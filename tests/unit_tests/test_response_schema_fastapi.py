"""FastAPI integration tests for get_response_schema

このテストファイルは実際のFastAPIアプリケーションを起動し、
get_response_schema()で生成されたスキーマがresponse_modelとして
正しく機能することを検証します。

Note:
    FastAPIはrepomの必須依存ではないため、このテストはスキップされる場合があります。
    FastAPIを使用するプロジェクトでのみ実行してください。

使用方法:
    # FastAPIがインストールされている場合のみ実行
    poetry run pytest tests/unit_tests/test_response_schema_fastapi.py -v
    
    # FastAPIをインストール
    poetry add --group dev fastapi httpx
"""

import pytest

# FastAPIが利用可能かチェック
try:
    from fastapi import FastAPI, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# FastAPIが利用できない場合はすべてのテストをスキップ
pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI is not installed. Install with: poetry add --group dev fastapi httpx"
)

if FASTAPI_AVAILABLE:
    from tests._init import *
    from sqlalchemy import Column, String, Integer
    from repom.base_model import BaseModel
    from typing import List, Generic, TypeVar
    from pydantic import BaseModel as PydanticBaseModel

    # ========================================
    # テスト用モデル定義
    # ========================================

    class ProductModel(BaseModel):
        """商品モデル"""
        __tablename__ = 'products'

        use_id = True
        use_created_at = True

        name = Column(String(100), nullable=False)
        price = Column(Integer, nullable=False)
        stock = Column(Integer, nullable=False, default=0)

        @BaseModel.response_field(
            is_available=bool,
            tags=List[str]
        )
        def to_dict(self):
            data = super().to_dict()
            data.update({
                'is_available': self.stock > 0,
                'tags': ['new', 'featured'] if self.stock > 10 else ['new']
            })
            return data

    # ========================================
    # Pydantic レスポンススキーマ
    # ========================================

    # ProductResponse をモジュールレベルで生成（FastAPIの推奨パターン）
    ProductResponse = ProductModel.get_response_schema()

    # Generic List Response
    T = TypeVar('T')

    class GenericListResponse(PydanticBaseModel, Generic[T]):
        """汎用リストレスポンス"""
        items: List[T]
        total: int
        page: int = 1
        page_size: int = 10

    # ========================================
    # FastAPI アプリケーション
    # ========================================

    def create_test_app() -> FastAPI:
        """テスト用FastAPIアプリケーションを作成"""
        app = FastAPI(title="Test API")
        router = APIRouter()

        # ダミーデータ
        mock_products = [
            {
                'id': 1,
                'name': 'Product 1',
                'price': 1000,
                'stock': 15,
                'created_at': '2025-01-01T00:00:00',
                'is_available': True,
                'tags': ['new', 'featured']
            },
            {
                'id': 2,
                'name': 'Product 2',
                'price': 2000,
                'stock': 5,
                'created_at': '2025-01-02T00:00:00',
                'is_available': True,
                'tags': ['new']
            },
        ]

        @router.get("/products/{product_id}", response_model=ProductResponse)
        def get_product(product_id: int):
            """単一の商品を取得"""
            for product in mock_products:
                if product['id'] == product_id:
                    return product
            return None

        @router.get("/products", response_model=GenericListResponse[ProductResponse])
        def get_products(page: int = 1, page_size: int = 10):
            """商品リストを取得（Generic List Response パターン）"""
            return {
                'items': mock_products,
                'total': len(mock_products),
                'page': page,
                'page_size': page_size
            }

        @router.get("/products_simple", response_model=List[ProductResponse])
        def get_products_simple():
            """商品リストを取得（シンプルなリスト）"""
            return mock_products

        app.include_router(router)
        return app

    # ========================================
    # Level 3-1: 基本的なエンドポイントテスト
    # ========================================

    def test_fastapi_single_item_response():
        """単一アイテムのレスポンスが正しくシリアライズされることを確認"""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/products/1")

        assert response.status_code == 200
        data = response.json()

        # すべてのフィールドが含まれる
        assert 'id' in data
        assert 'name' in data
        assert 'price' in data
        assert 'stock' in data
        assert 'created_at' in data
        assert 'is_available' in data
        assert 'tags' in data

        # 値が正しい
        assert data['id'] == 1
        assert data['name'] == 'Product 1'
        assert data['is_available'] is True
        assert data['tags'] == ['new', 'featured']

    def test_fastapi_generic_list_response():
        """GenericListResponse パターンが正しく動作することを確認"""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/products?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()

        # GenericListResponse の構造
        assert 'items' in data
        assert 'total' in data
        assert 'page' in data
        assert 'page_size' in data

        # 値が正しい
        assert len(data['items']) == 2
        assert data['total'] == 2
        assert data['page'] == 1
        assert data['page_size'] == 10

        # items[0] の内容を確認
        item = data['items'][0]
        assert item['id'] == 1
        assert item['name'] == 'Product 1'
        assert item['is_available'] is True

    def test_fastapi_simple_list_response():
        """シンプルなリストレスポンスが正しく動作することを確認"""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/products_simple")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['id'] == 1
        assert data[0]['name'] == 'Product 1'

    # ========================================
    # Level 3-2: OpenAPI スキーマ検証
    # ========================================

    def test_fastapi_openapi_schema_generation():
        """FastAPIのOpenAPIスキーマが正しく生成されることを確認"""
        app = create_test_app()
        client = TestClient(app)

        # OpenAPI JSON を取得
        response = client.get("/openapi.json")

        assert response.status_code == 200
        openapi_schema = response.json()

        # パスが存在する
        assert '/products/{product_id}' in openapi_schema['paths']
        assert '/products' in openapi_schema['paths']

        # レスポンススキーマが定義されている
        assert 'components' in openapi_schema
        assert 'schemas' in openapi_schema['components']

        # ProductResponse スキーマが含まれている
        schemas = openapi_schema['components']['schemas']

        # スキーマ名を確認（ProductResponse または ProductWithIdResponse など）
        schema_names = list(schemas.keys())
        assert any('Product' in name for name in schema_names), \
            f"ProductResponse schema not found in {schema_names}"

    def test_fastapi_response_validation_error():
        """不正なレスポンスデータの場合にバリデーションエラーが発生することを確認"""
        app = FastAPI()

        @app.get("/invalid", response_model=ProductResponse)
        def get_invalid():
            # 必須フィールドが欠けているデータを返す
            return {
                'id': 1,
                # 'name' が欠けている（必須）
                'price': 1000
            }

        client = TestClient(app, raise_server_exceptions=False)

        # バリデーションエラーが発生する
        response = client.get("/invalid")

        # FastAPIはバリデーションエラーを500エラーとして返す
        assert response.status_code == 500

    # ========================================
    # Level 3-3: 複雑な前方参照のFastAPIテスト
    # ========================================

    class CategoryModel(BaseModel):
        """カテゴリモデル"""
        __tablename__ = 'categories'

        use_id = True
        name = Column(String(100), nullable=False)

        @BaseModel.response_field(
            products=List['ProductResponse']  # 前方参照
        )
        def to_dict(self):
            data = super().to_dict()
            data.update({
                'products': []  # 簡略化
            })
            return data

    def test_fastapi_forward_refs_in_endpoint():
        """前方参照を使用したスキーマがFastAPIで正しく動作することを確認"""
        # ProductResponse を先に生成
        ProductResp = ProductModel.get_response_schema()

        # CategoryResponse を前方参照を解決して生成
        CategoryResponse = CategoryModel.get_response_schema(
            forward_refs={'ProductResponse': ProductResp}
        )

        app = FastAPI()

        @app.get("/categories/{category_id}", response_model=CategoryResponse)
        def get_category(category_id: int):
            return {
                'id': category_id,
                'name': 'Electronics',
                'products': []
            }

        client = TestClient(app)
        response = client.get("/categories/1")

        assert response.status_code == 200
        data = response.json()

        assert data['id'] == 1
        assert data['name'] == 'Electronics'
        assert data['products'] == []

    # ========================================
    # Level 3-4: パフォーマンステスト
    # ========================================

    def test_fastapi_schema_caching_performance(benchmark):
        """スキーマキャッシュがパフォーマンスに寄与することを確認"""

        def create_schema():
            return ProductModel.get_response_schema()

        # 最初の呼び出しでキャッシュが作成される
        first_schema = create_schema()

        # 2回目以降はキャッシュから返される（非常に高速）
        result = benchmark(create_schema)

        # キャッシュが効いていることを確認
        assert result is first_schema

    # ========================================
    # Level 3-5: エンドツーエンドテスト
    # ========================================

    def test_fastapi_end_to_end_with_database(db_test):
        """実際のデータベースと連携したエンドツーエンドテスト"""
        from repom.base_repository import BaseRepository

        # リポジトリを作成
        repo = BaseRepository[ProductModel]()

        # データを作成
        product = ProductModel(name='Test Product', price=1500, stock=20)
        db_test.add(product)
        db_test.commit()
        db_test.refresh(product)

        # to_dict() でデータを取得
        product_data = product.to_dict()

        # ProductResponse でバリデーション
        validated = ProductResponse(**product_data)

        # すべてのフィールドが正しい
        assert validated.id == product.id
        assert validated.name == 'Test Product'
        assert validated.price == 1500
        assert validated.stock == 20
        assert validated.is_available is True
        assert 'new' in validated.tags
        assert 'featured' in validated.tags


# ========================================
# FastAPIがインストールされていない場合のダミーテスト
# ========================================

if not FASTAPI_AVAILABLE:
    def test_fastapi_not_installed():
        """FastAPIがインストールされていないことを通知"""
        pytest.skip("FastAPI is not installed")
