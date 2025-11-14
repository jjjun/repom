# get_response_schema() テスト戦略ガイド

## 概要

`BaseModel.get_response_schema()` は FastAPI の `response_model` で使用することを想定した Pydantic スキーマを動的生成するメソッドです。このガイドでは、効果的なテスト戦略とベストプラクティスを説明します。

## テスト戦略の3つのレベル

### Level 1: ユニットテスト（基本機能）

**ファイル**: `tests/unit_tests/test_response_field.py`

**目的**: スキーマ生成の基本機能を検証

**テスト内容**:
- ✅ `@response_field` デコレータのメタデータ保存
- ✅ SQLAlchemy カラムのスキーマへの反映
- ✅ 追加フィールド（`@response_field` で宣言）の含有
- ✅ スキーマ名のカスタマイズ
- ✅ スキーマキャッシュの動作
- ✅ Pydantic バリデーション

**実行方法**:
```bash
poetry run pytest tests/unit_tests/test_response_field.py -v
```

**カバレッジ**: 13テスト

---

### Level 2: 前方参照テスト（FastAPI使用の核心）

**ファイル**: `tests/unit_tests/test_response_schema_forward_refs.py`

**目的**: FastAPI での実際の使用シナリオにおける前方参照の解決を検証

**テスト内容**:
- ✅ `List`、`Dict`、`Optional` などの標準型の前方参照
- ✅ カスタムモデルの前方参照（`List['CustomResponse']`）
- ✅ ネストした型の前方参照（`List[Dict[str, Any]]`）
- ✅ 循環参照の解決
- ✅ 前方参照とキャッシュの相互作用
- ✅ エラーハンドリング（`model_rebuild` の警告）
- ✅ `GenericListResponse[T]` パターン

**実行方法**:
```bash
poetry run pytest tests/unit_tests/test_response_schema_forward_refs.py -v
```

**カバレッジ**: 14テスト

**重要なテストケース**:

#### 2-1: 標準型の前方参照
```python
@BaseModel.response_field(
    tags=List[str],         # ✅ forward_refs なしで動作
    metadata=Dict[str, Any] # ✅ forward_refs なしで動作
)
def to_dict(self):
    ...
```

#### 2-2: カスタムモデルの前方参照
```python
@BaseModel.response_field(
    related_books=List['BookResponse']  # 文字列で前方参照
)
def to_dict(self):
    ...

# 前方参照を解決
ReviewResponse = ReviewModel.get_response_schema(
    forward_refs={'BookResponse': BookResponse}
)
```

#### 2-3: GenericListResponse パターン
```python
from pydantic import BaseModel as PydanticBaseModel
from typing import Generic, TypeVar

T = TypeVar('T')

class GenericListResponse(PydanticBaseModel, Generic[T]):
    items: List[T]
    total: int

# FastAPI で使用
BookResponse = BookModel.get_response_schema()
ListResponse = GenericListResponse[BookResponse]

@router.get("/books", response_model=ListResponse)
def get_books():
    ...
```

---

### Level 3: FastAPI 統合テスト（オプション）

**ファイル**: `tests/unit_tests/test_response_schema_fastapi.py`

**目的**: 実際の FastAPI アプリケーションでの動作を検証

**前提条件**:
```bash
# FastAPI と httpx をインストール（開発依存）
poetry add --group dev fastapi httpx
```

**テスト内容**:
- ✅ FastAPI エンドポイントでのスキーマ使用
- ✅ `response_model` としての機能
- ✅ JSON シリアライゼーション
- ✅ OpenAPI スキーマ生成
- ✅ バリデーションエラーの処理
- ✅ データベースとの連携（E2E テスト）

**実行方法**:
```bash
# FastAPI がインストールされている場合のみ実行
poetry run pytest tests/unit_tests/test_response_schema_fastapi.py -v

# FastAPI がない場合は自動的にスキップ
# SKIPPED (FastAPI is not installed. Install with: poetry add --group dev fastapi httpx)
```

**カバレッジ**: 9テスト（FastAPI インストール時）

---

## テスト実行コマンド一覧

### すべてのテストを実行
```bash
# response_schema 関連のすべてのテスト
poetry run pytest tests/unit_tests/test_response_field.py \
                  tests/unit_tests/test_response_schema_forward_refs.py \
                  tests/unit_tests/test_response_schema_fastapi.py -v

# 合計: 27テスト（FastAPI なし）/ 36テスト（FastAPI あり）
```

### Level 別に実行
```bash
# Level 1: 基本機能のみ
poetry run pytest tests/unit_tests/test_response_field.py -v

# Level 2: 前方参照のみ
poetry run pytest tests/unit_tests/test_response_schema_forward_refs.py -v

# Level 3: FastAPI 統合（オプション）
poetry run pytest tests/unit_tests/test_response_schema_fastapi.py -v
```

### パターン別に実行
```bash
# 特定のパターンのみテスト
poetry run pytest -k "forward_refs" -v
poetry run pytest -k "fastapi" -v
poetry run pytest -k "generic_list" -v
```

---

## ベストプラクティス

### 1. スキーマ生成はモジュールレベルで行う

✅ **推奨**:
```python
# api/schemas/book.py
from models.book import BookModel

# モジュールレベルで生成（インポート時に1回だけ）
BookResponse = BookModel.get_response_schema()
```

❌ **非推奨**:
```python
# エンドポイント内で生成（リクエストごとに実行される）
@router.get("/books")
def get_books():
    BookResponse = BookModel.get_response_schema()  # ❌ 無駄
    ...
```

**理由**: スキーマはキャッシュされますが、モジュールレベルで生成する方がコードが明確で、FastAPI の `response_model` デコレータでも使いやすくなります。

---

### 2. 前方参照は必要最小限に

✅ **推奨**:
```python
# カスタムモデルの前方参照のみ指定
ReviewResponse = ReviewModel.get_response_schema(
    forward_refs={'BookResponse': BookResponse}
)
```

❌ **不要**:
```python
# List や Dict を含める必要はない
ReviewResponse = ReviewModel.get_response_schema(
    forward_refs={
        'List': List,           # ❌ 不要
        'Dict': Dict,           # ❌ 不要
        'BookResponse': BookResponse  # ✅ 必要
    }
)
```

**理由**: Pydantic は標準型（`List`、`Dict`、`Optional` など）を自動的に解決します。カスタムモデルの前方参照のみ指定してください。

---

### 3. 循環参照は文字列アノテーションで解決

✅ **推奨**:
```python
# models/book.py
class BookModel(BaseModel):
    @response_field(
        reviews=List['ReviewResponse']  # 文字列で前方参照
    )
    def to_dict(self):
        ...

# api/schemas/book.py
from models.book import BookModel
from api.schemas.review import ReviewResponse

# スキーマ生成時に解決
BookResponse = BookModel.get_response_schema(
    forward_refs={'ReviewResponse': ReviewResponse}
)
```

**理由**: モデル定義時にインポートすると循環参照エラーが発生します。文字列アノテーションを使い、スキーマ生成時に解決します。

---

### 4. GenericListResponse パターンを活用

✅ **推奨**:
```python
# api/schemas/generic.py
from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar('T')

class GenericListResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 10

# api/endpoints/books.py
from api.schemas.book import BookResponse
from api.schemas.generic import GenericListResponse

@router.get("/books", response_model=GenericListResponse[BookResponse])
def get_books(page: int = 1, page_size: int = 10):
    books = repo.get_all()
    return {
        'items': [book.to_dict() for book in books],
        'total': len(books),
        'page': page,
        'page_size': page_size
    }
```

**理由**: リストエンドポイントの一貫した構造を提供し、ページネーション情報も含められます。

---

## トラブルシューティング

### 問題1: `List` が解決されない

**症状**:
```python
ValidationError: List is not defined
```

**原因**: 一部の環境では `List` が解決されない場合があります。

**解決策**:
```python
from typing import List

BookResponse = BookModel.get_response_schema(
    forward_refs={'List': List}
)
```

---

### 問題2: カスタムモデルの前方参照が解決されない

**症状**:
```python
# related_books フィールドが文字列 'BookResponse' のまま
```

**原因**: `forward_refs` パラメータを指定していない。

**解決策**:
```python
# BookResponse を先に生成
BookResponse = BookModel.get_response_schema()

# 前方参照を解決
ReviewResponse = ReviewModel.get_response_schema(
    forward_refs={'BookResponse': BookResponse}
)
```

---

### 問題3: キャッシュの問題

**症状**: スキーマが更新されない。

**原因**: 異なる `forward_refs` が同じキャッシュキーを生成している。

**解決策**:
```python
# キャッシュをクリア（開発時のみ）
MyModel._response_schemas.clear()

# または Python を再起動
```

---

## テストの追加方法

新しい機能や修正を追加する場合は、適切なレベルのテストファイルにテストケースを追加してください。

### 基本機能のテスト追加
→ `tests/unit_tests/test_response_field.py`

### 前方参照の新しいパターン
→ `tests/unit_tests/test_response_schema_forward_refs.py`

### FastAPI 固有の動作
→ `tests/unit_tests/test_response_schema_fastapi.py`

---

## まとめ

- **Level 1（基本）**: 常に実行（CI/CD で必須）
- **Level 2（前方参照）**: 常に実行（CI/CD で必須）
- **Level 3（FastAPI）**: オプション（FastAPI を使用するプロジェクトでのみ）

**合計テストカバレッジ**:
- FastAPI なし: **27テスト**
- FastAPI あり: **36テスト**

すべてのテストが成功することで、`get_response_schema()` が FastAPI の `response_model` として確実に機能することが保証されます。
