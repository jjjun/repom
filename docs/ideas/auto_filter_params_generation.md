# FilterParams 自動生成

## ステータス
- **段階**: アイディア
- **優先度**: 中
- **複雑度**: 中
- **作成日**: 2025-11-15
- **最終更新**: 2025-11-15

## 概要

BaseRepository の `_build_filters` で使用されるフィルタ定義を元に、FastAPI の検索エンドポイント用の `FilterParams` クラスを自動生成します。

## モチベーション

現在の実装では、リポジトリでフィルタロジックを定義する場合:

**現在のワークフロー**（手動）:
```python
# リポジトリでフィルタロジックを定義
class SampleRepository(BaseRepository[Sample]):
    def _build_filters(self, params: Optional[SampleFilterParams]) -> list:
        filters = []
        if params.name:
            filters.append(Sample.name.like(f"%{params.name}%"))
        if params.status:
            filters.append(Sample.status == params.status)
        return filters

# 別途 FilterParams を手動で定義
class SampleFilterParams(FilterParams):
    name: Optional[str] = None
    status: Optional[str] = None
```

**問題点**:
- フィルタロジックと FilterParams の定義が重複
- 同期を手動で保つ必要がある
- フィルタを追加・変更する際に2箇所を更新
- タイポや型の不一致が発生しやすい

**理想のワークフロー**（自動生成）:
```python
# リポジトリでフィルタ定義のみ
class SampleRepository(BaseRepository[Sample]):
    _filter_schema = {
        'name': {'type': str, 'filter': 'like', 'description': '名前で部分一致検索'},
        'status': {'type': str, 'filter': 'exact', 'description': 'ステータスで完全一致'},
        'created_after': {'type': datetime, 'filter': 'gte', 'field': 'created_at'},
    }

# FilterParams が自動生成される
SampleFilterParams = SampleRepository.get_filter_params()
# FastAPI で使用
@app.get("/samples/")
def list_samples(filters: SampleFilterParams = Depends(SampleFilterParams.as_query_depends())):
    return sample_repo.find(filters=sample_repo._build_filters(filters))
```

**自動生成の利点**:
- フィルタ定義が一箇所で完結（Single Source of Truth）
- 手動同期が不要
- タイポや型の不一致を防止
- より宣言的でメンテナンスしやすい
- フィルタロジックと API パラメータの自動同期

## ユースケース

### 1. 基本的な検索フィルタ
```python
class ProductRepository(BaseRepository[Product]):
    _filter_schema = {
        'name': {'type': str, 'filter': 'like'},
        'category': {'type': str, 'filter': 'exact'},
        'min_price': {'type': float, 'filter': 'gte', 'field': 'price'},
        'max_price': {'type': float, 'filter': 'lte', 'field': 'price'},
        'in_stock': {'type': bool, 'filter': 'exact'},
    }

# 自動生成された FilterParams を使用
ProductFilterParams = ProductRepository.get_filter_params()

# FastAPI エンドポイント
@app.get("/products/", response_model=list[ProductResponse])
def list_products(
    filters: ProductFilterParams = Depends(ProductFilterParams.as_query_depends())
):
    products = product_repo.find(filters=product_repo._build_filters(filters))
    return products
```

### 2. 日付範囲検索
```python
class OrderRepository(BaseRepository[Order]):
    _filter_schema = {
        'status': {'type': str, 'filter': 'exact'},
        'customer_id': {'type': int, 'filter': 'exact'},
        'order_date_from': {'type': datetime, 'filter': 'gte', 'field': 'order_date'},
        'order_date_to': {'type': datetime, 'filter': 'lte', 'field': 'order_date'},
        'min_total': {'type': Decimal, 'filter': 'gte', 'field': 'total_amount'},
    }

# 自動生成・自動適用
OrderFilterParams = OrderRepository.get_filter_params()
```

### 3. IN/NOT IN フィルタ
```python
class TaskRepository(BaseRepository[Task]):
    _filter_schema = {
        'title': {'type': str, 'filter': 'like'},
        'status_in': {'type': List[str], 'filter': 'in', 'field': 'status'},
        'assignee_id': {'type': int, 'filter': 'exact'},
        'tag_in': {'type': List[str], 'filter': 'in', 'field': 'tags'},
    }
```

## 検討可能なアプローチ

### アプローチ 1: スキーマベース生成
**説明**: クラス変数 `_filter_schema` からフィルタ定義と FilterParams を生成

**長所**:
- 宣言的で読みやすい
- 型安全性が高い
- IDE の補完が効く
- フィルタ定義が一箇所に集約

**短所**:
- 新しい記法を学ぶ必要がある
- 複雑なフィルタロジックには向かない可能性

**例**:
```python
class SampleRepository(BaseRepository[Sample]):
    _filter_schema = {
        'name': {
            'type': str,
            'filter': 'like',  # like, exact, gte, lte, in, etc.
            'description': '名前で検索',
            'nullable': True,
        },
        'status': {
            'type': str,
            'filter': 'exact',
            'description': 'ステータス',
        },
    }
    
    def _build_filters(self, params: Optional[FilterParams]) -> list:
        # 自動生成されたロジックを使用
        return self._auto_build_filters(params)
```

### アプローチ 2: デコレータベース生成
**説明**: デコレータでフィルタを定義し、FilterParams を自動生成

**長所**:
- Python らしい記法
- 既存の `_build_filters` メソッドを拡張可能
- カスタムロジックを追加しやすい

**短所**:
- デコレータが増えると読みづらくなる可能性
- スキーマの全体像が見えにくい

**例**:
```python
class SampleRepository(BaseRepository[Sample]):
    @filter_field('name', type=str, filter='like')
    @filter_field('status', type=str, filter='exact')
    @filter_field('created_after', type=datetime, filter='gte', field='created_at')
    def _build_filters(self, params: Optional[FilterParams]) -> list:
        # デコレータが自動的に基本フィルタを適用
        # 必要に応じてカスタムロジックを追加
        filters = super()._build_filters(params)
        if params.custom_logic:
            filters.append(...)
        return filters
```

### アプローチ 3: ハイブリッドアプローチ
**説明**: スキーマベースを基本とし、カスタムロジックをメソッドで追加

**長所**:
- 宣言的な定義とカスタムロジックの両立
- 柔軟性が高い
- 段階的な移行が可能

**短所**:
- 複数の方法が混在する可能性

**例**:
```python
class SampleRepository(BaseRepository[Sample]):
    _filter_schema = {
        'name': {'type': str, 'filter': 'like'},
        'status': {'type': str, 'filter': 'exact'},
    }
    
    def _build_filters(self, params: Optional[FilterParams]) -> list:
        # 基本フィルタは自動生成
        filters = self._auto_build_filters(params)
        
        # カスタムロジックを追加
        if params and hasattr(params, 'custom_search'):
            if params.custom_search:
                filters.append(or_(
                    Sample.name.like(f"%{params.custom_search}%"),
                    Sample.description.like(f"%{params.custom_search}%")
                ))
        
        return filters
```

## 技術的考慮事項

### フィルタタイプの対応

| フィルタタイプ | SQLAlchemy 表現 | 説明 |
|--------------|----------------|------|
| `exact` | `column == value` | 完全一致 |
| `like` | `column.like(f"%{value}%")` | 部分一致 |
| `ilike` | `column.ilike(f"%{value}%")` | 大文字小文字を区別しない部分一致 |
| `gte` | `column >= value` | 以上 |
| `lte` | `column <= value` | 以下 |
| `gt` | `column > value` | より大きい |
| `lt` | `column < value` | より小さい |
| `in` | `column.in_(value)` | リスト内のいずれか |
| `not_in` | `~column.in_(value)` | リスト内のいずれでもない |
| `is_null` | `column.is_(None)` | NULL |
| `is_not_null` | `column.isnot(None)` | NOT NULL |

### 型バリデーション
- Pydantic を使用した型バリデーション
- フィルタ定義の型と FilterParams の型を自動一致
- List 型の適切な処理（FastAPI の Query パラメータ対応）

### セキュリティ考慮事項
- 許可されたフィールドのみフィルタ可能
- SQL インジェクション防止（SQLAlchemy のパラメータバインディング使用）
- プライベートフィールドの自動除外（`_` で始まるフィールド）
- `_excluded_from_query` による明示的な除外

### パフォーマンス
- FilterParams の生成は起動時に1回のみ（キャッシュ）
- フィルタ適用のオーバーヘッドは最小限
- インデックスを考慮したフィルタ設計の推奨

## 統合ポイント

### 影響を受けるコンポーネント
- `repom/base_repository.py` - `_filter_schema` サポートと自動生成ロジック追加
- `repom/base_repository.py` - `FilterParams` の拡張（既存機能）
- `README.md` - 新機能のドキュメント化
- `docs/guides/repository_and_utilities_guide.md` - ガイドの更新

### 既存機能との相互作用
- 既存の `_build_filters` メソッドと後方互換性を維持
- `FilterParams.as_query_depends()` と統合
- 既存のリポジトリパターンを拡張

### 実装例
```python
# repom/base_repository.py に追加

class BaseRepository(Generic[T]):
    _filter_schema: Dict[str, Dict[str, Any]] = {}
    _generated_filter_params: Optional[Type[FilterParams]] = None
    
    @classmethod
    def get_filter_params(cls) -> Type[FilterParams]:
        """
        _filter_schema から FilterParams クラスを自動生成
        
        Returns:
            Type[FilterParams]: 生成された FilterParams クラス
        """
        if cls._generated_filter_params is not None:
            return cls._generated_filter_params
        
        if not cls._filter_schema:
            return FilterParams
        
        # 動的にフィールドを生成
        fields = {}
        for param_name, config in cls._filter_schema.items():
            field_type = config['type']
            description = config.get('description', f'Filter by {param_name}')
            default = config.get('default', None)
            
            # Optional 型に変換
            if not config.get('required', False):
                field_type = Optional[field_type]
            
            fields[param_name] = (field_type, Field(default=default, description=description))
        
        # 動的にクラスを生成
        filter_class = create_model(
            f'{cls.__name__}FilterParams',
            __base__=FilterParams,
            **fields
        )
        
        cls._generated_filter_params = filter_class
        return filter_class
    
    def _auto_build_filters(self, params: Optional[FilterParams]) -> list:
        """
        _filter_schema と params から自動的にフィルタを構築
        
        Args:
            params: FilterParams インスタンス
            
        Returns:
            list: SQLAlchemy フィルタ式のリスト
        """
        if not params or not self._filter_schema:
            return []
        
        filters = []
        for param_name, config in self._filter_schema.items():
            value = getattr(params, param_name, None)
            if value is None:
                continue
            
            field_name = config.get('field', param_name)
            filter_type = config.get('filter', 'exact')
            
            if not hasattr(self.model, field_name):
                continue
            
            column = getattr(self.model, field_name)
            
            # フィルタタイプに応じた式を生成
            if filter_type == 'exact':
                filters.append(column == value)
            elif filter_type == 'like':
                filters.append(column.like(f'%{value}%'))
            elif filter_type == 'ilike':
                filters.append(column.ilike(f'%{value}%'))
            elif filter_type == 'gte':
                filters.append(column >= value)
            elif filter_type == 'lte':
                filters.append(column <= value)
            elif filter_type == 'gt':
                filters.append(column > value)
            elif filter_type == 'lt':
                filters.append(column < value)
            elif filter_type == 'in':
                filters.append(column.in_(value))
            elif filter_type == 'not_in':
                filters.append(~column.in_(value))
            elif filter_type == 'is_null' and value is True:
                filters.append(column.is_(None))
            elif filter_type == 'is_not_null' and value is True:
                filters.append(column.isnot(None))
        
        return filters
```

### 使用例
```python
# models/product.py
class Product(BaseModel):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    category = Column(String(100))
    price = Column(Numeric(10, 2))
    in_stock = Column(Boolean, default=True)

# repositories/product.py
class ProductRepository(BaseRepository[Product]):
    _filter_schema = {
        'name': {
            'type': str,
            'filter': 'like',
            'description': '商品名で部分一致検索'
        },
        'category': {
            'type': str,
            'filter': 'exact',
            'description': 'カテゴリで完全一致'
        },
        'min_price': {
            'type': float,
            'filter': 'gte',
            'field': 'price',
            'description': '最低価格'
        },
        'max_price': {
            'type': float,
            'filter': 'lte',
            'field': 'price',
            'description': '最高価格'
        },
        'in_stock': {
            'type': bool,
            'filter': 'exact',
            'description': '在庫あり'
        },
    }
    
    # 自動生成されたフィルタを使用
    def _build_filters(self, params: Optional[FilterParams]) -> list:
        return self._auto_build_filters(params)

# FastAPI エンドポイント
ProductFilterParams = ProductRepository.get_filter_params()

@app.get("/products/")
def list_products(
    filters: ProductFilterParams = Depends(ProductFilterParams.as_query_depends())
):
    products = product_repo.find(filters=product_repo._build_filters(filters))
    return products

# 自動生成される OpenAPI ドキュメント:
# GET /products/?name=laptop&category=electronics&min_price=100&max_price=1000&in_stock=true
```

## 次のステップ

- [ ] フィルタタイプの完全なリストを定義
- [ ] `_auto_build_filters` メソッドのプロトタイプ実装
- [ ] `get_filter_params()` クラスメソッドの実装
- [ ] 既存の `_build_filters` との統合パターンを設計
- [ ] サンプルリポジトリでテスト
- [ ] カスタムフィルタロジックとの組み合わせパターンをテスト
- [ ] セキュリティテスト（不正なフィールドアクセスなど）
- [ ] パフォーマンステスト
- [ ] ドキュメントの更新
- [ ] 実装する場合は `docs/research/` に移動

## 関連ドキュメント

- `repom/base_repository.py` - BaseRepository の現在の実装
- `docs/guides/repository_and_utilities_guide.md` - FilterParams の使い方
- `README.md` - BaseRepository のドキュメント

## 解決すべき質問

1. 既存の手動 `_build_filters` 実装との互換性をどう保つか？
2. 複雑なカスタムフィルタ（OR 条件、ネストなど）をどう扱うか？
3. フィルタスキーマのバリデーションをいつ行うか（起動時 vs 実行時）？
4. 動的に生成された FilterParams クラスの型ヒントをどう扱うか？
5. フィルタスキーマを外部ファイル（YAML/JSON）で定義すべきか？
6. リレーションシップを持つモデルのフィルタをどうサポートするか？
7. フィルタの組み合わせ（AND/OR）をどう表現するか？

## 追加アイディア

### スキーマの外部定義
YAML や JSON でフィルタスキーマを定義:
```yaml
# filters/product.yml
ProductRepository:
  name:
    type: str
    filter: like
    description: 商品名で検索
  category:
    type: str
    filter: exact
```

### フィルタプリセット
よく使うフィルタの組み合わせをプリセットとして定義:
```python
class ProductRepository(BaseRepository[Product]):
    _filter_presets = {
        'available': {'in_stock': True, 'status': 'active'},
        'on_sale': {'discount_rate_gt': 0},
    }
```

### 動的フィルタバリデーション
実行時にフィルタ値をバリデート:
```python
_filter_schema = {
    'price': {
        'type': float,
        'filter': 'gte',
        'validators': [lambda x: x > 0, 'Price must be positive']
    }
}
```

### 関連モデルのフィルタ
JOIN を含むフィルタのサポート:
```python
_filter_schema = {
    'category__name': {  # __ で関連モデルを表現
        'type': str,
        'filter': 'exact',
        'join': 'category'
    }
}
```
