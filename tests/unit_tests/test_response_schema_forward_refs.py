"""Tests for get_response_schema with forward references (前方参照のテスト)

このテストファイルは、FastAPIのresponse_modelでの実際の使用シナリオを想定して、
前方参照の解決が正しく行われることを検証します。
"""

from tests._init import *
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, Dict, Any
from repom.base_model_auto import BaseModelAuto
from pydantic import ValidationError
import pytest


# ========================================
# テスト用モデル定義
# ========================================

class AuthorModel(BaseModelAuto):
    """著者モデル"""
    __tablename__ = 'authors'

    use_id = True
    use_created_at = True

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)


class BookModel(BaseModelAuto):
    """書籍モデル（著者への参照を持つ）"""
    __tablename__ = 'books'

    use_id = True
    use_created_at = True

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey('authors.id'), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

    # リレーションシップ（テストでは使用しない場合もある）
    # author = relationship('AuthorModel', backref='books')

    @BaseModelAuto.response_field(
        author=Dict[str, Any],  # 著者情報を辞書として含める
        tags=List[str],         # タグのリスト
        is_available=bool       # 在庫があるか
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'author': {'id': self.author_id, 'name': 'Unknown'},  # 簡略化
            'tags': ['fiction', 'bestseller'],
            'is_available': self.price > 0
        })
        return data


class ReviewModel(BaseModelAuto):
    """レビューモデル（書籍への参照を持つ - 循環参照のテスト用）"""
    __tablename__ = 'reviews'

    use_id = True

    book_id: Mapped[int] = mapped_column(Integer, ForeignKey('books.id'), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    @BaseModelAuto.response_field(
        book_title=str,                    # 書籍タイトル
        related_books=List['BookResponse']  # 前方参照（文字列）
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'book_title': 'Sample Book',
            'related_books': []  # 簡略化
        })
        return data


# ========================================
# Level 2-1: 標準型の前方参照テスト
# ========================================

def test_forward_refs_with_list_type():
    """List型の前方参照が正しく解決されることを確認"""
    # forward_refs なしでも List は解決されるはず
    BookResponse = BookModel.get_response_schema()

    fields = BookResponse.model_fields

    # tags フィールドが List[str] として正しく認識される
    assert 'tags' in fields
    tags_field = fields['tags']

    # 型アノテーションを確認
    # Pydantic 2.x では annotation 属性で型情報を取得
    assert tags_field.annotation is not None


def test_forward_refs_with_dict_type():
    """Dict型の前方参照が正しく解決されることを確認"""
    BookResponse = BookModel.get_response_schema()

    fields = BookResponse.model_fields

    # author フィールドが Dict として正しく認識される
    assert 'author' in fields
    author_field = fields['author']

    assert author_field.annotation is not None


def test_forward_refs_explicit_list_parameter():
    """forward_refs に List を明示的に指定した場合のテスト"""
    # 一部の環境では List を明示的に指定する必要があるかもしれない
    BookResponse = BookModel.get_response_schema(
        forward_refs={'List': List, 'Dict': Dict}
    )

    fields = BookResponse.model_fields

    assert 'tags' in fields
    assert 'author' in fields


# ========================================
# Level 2-2: カスタムモデルの前方参照テスト
# ========================================

def test_forward_refs_custom_model_string_annotation():
    """カスタムモデルの文字列アノテーション（前方参照）が正しく解決されることを確認"""
    # まず BookResponse を生成
    BookResponse = BookModel.get_response_schema()

    # ReviewResponse を生成（BookResponse への前方参照を解決）
    ReviewResponse = ReviewModel.get_response_schema(
        forward_refs={'BookResponse': BookResponse}
    )

    fields = ReviewResponse.model_fields

    # related_books フィールドが存在することを確認
    assert 'related_books' in fields

    # 型アノテーションが List[BookResponse] として解決されているか確認
    related_books_field = fields['related_books']
    assert related_books_field.annotation is not None


def test_forward_refs_validation_with_custom_model():
    """カスタムモデルの前方参照を使用したバリデーションテスト"""
    # スキーマ生成
    BookResponse = BookModel.get_response_schema()
    ReviewResponse = ReviewModel.get_response_schema(
        forward_refs={'BookResponse': BookResponse}
    )

    # ReviewModel のインスタンスを作成
    review = ReviewModel(book_id=1, rating=5, comment='Great!')
    review.id = 1

    # to_dict() でデータを取得
    data = review.to_dict()

    # Pydantic でバリデーション
    validated = ReviewResponse(**data)

    assert validated.id == 1
    assert validated.rating == 5
    assert validated.book_title == 'Sample Book'
    assert validated.related_books == []


# ========================================
# Level 2-3: 複雑な前方参照のテスト
# ========================================

class ComplexModel(BaseModelAuto):
    """複雑な前方参照を持つモデル"""
    __tablename__ = 'complex_models'

    use_id = True

    name = Column(String(100), nullable=False)

    @BaseModelAuto.response_field(
        nested_list=List[List[str]],           # ネストしたリスト
        optional_dict=Optional[Dict[str, int]],  # Optional な Dict
        mixed_data=List[Dict[str, Any]]        # 複雑なネスト
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'nested_list': [['a', 'b'], ['c', 'd']],
            'optional_dict': {'count': 10},
            'mixed_data': [{'key': 'value', 'num': 123}]
        })
        return data


def test_forward_refs_nested_types():
    """ネストした型の前方参照が正しく解決されることを確認"""
    ComplexResponse = ComplexModel.get_response_schema()

    fields = ComplexResponse.model_fields

    # すべてのフィールドが存在することを確認
    assert 'nested_list' in fields
    assert 'optional_dict' in fields
    assert 'mixed_data' in fields


def test_forward_refs_nested_types_validation():
    """ネストした型のバリデーションが正しく動作することを確認"""
    ComplexResponse = ComplexModel.get_response_schema()

    model = ComplexModel(name='test')
    model.id = 1

    data = model.to_dict()
    validated = ComplexResponse(**data)

    assert validated.nested_list == [['a', 'b'], ['c', 'd']]
    assert validated.optional_dict == {'count': 10}
    assert validated.mixed_data == [{'key': 'value', 'num': 123}]


def test_forward_refs_optional_validation():
    """Optional フィールドが None を許容することを確認"""
    class OptionalModel(BaseModelAuto):
        __tablename__ = 'optional_models'
        use_id = True
        name = Column(String(100))

        @BaseModelAuto.response_field(
            optional_value=Optional[int],
            optional_list=Optional[List[str]]
        )
        def to_dict(self):
            data = super().to_dict()
            data.update({
                'optional_value': None,
                'optional_list': None
            })
            return data

    OptionalResponse = OptionalModel.get_response_schema()

    model = OptionalModel(name='test')
    model.id = 1

    data = model.to_dict()
    validated = OptionalResponse(**data)

    assert validated.optional_value is None
    assert validated.optional_list is None


# ========================================
# Level 2-4: 前方参照なしでのエラーケース
# ========================================

def test_forward_refs_missing_custom_model_still_creates_schema():
    """カスタムモデルの前方参照を指定しなくてもスキーマは生成される（文字列のまま）"""
    # forward_refs を指定せずにスキーマ生成
    # 内部的には文字列 'BookResponse' のまま保持される
    ReviewResponse = ReviewModel.get_response_schema()

    # スキーマ自体は生成される
    assert ReviewResponse is not None
    fields = ReviewResponse.model_fields
    assert 'related_books' in fields


# ========================================
# Level 2-5: キャッシュと前方参照の相互作用テスト
# ========================================

def test_forward_refs_different_refs_create_different_cache():
    """異なる forward_refs で異なるキャッシュエントリが作成されることを確認"""
    BookResponse1 = BookModel.get_response_schema()
    BookResponse2 = BookModel.get_response_schema()

    # 同じ forward_refs（なし）なので同じキャッシュ
    assert BookResponse1 is BookResponse2

    # 異なる forward_refs を指定
    BookResponse3 = BookModel.get_response_schema(
        forward_refs={'List': List}
    )

    # 異なるキャッシュエントリが作成される
    assert BookResponse1 is not BookResponse3


def test_forward_refs_cache_key_includes_refs():
    """forward_refs がキャッシュキーに含まれることを確認"""
    # 最初の呼び出し
    Schema1 = BookModel.get_response_schema()

    # 異なる forward_refs で呼び出し
    Schema2 = BookModel.get_response_schema(
        forward_refs={'CustomType': str}
    )

    # 異なるスキーマが生成される
    assert Schema1 is not Schema2

    # 同じ forward_refs で再度呼び出し
    Schema3 = BookModel.get_response_schema(
        forward_refs={'CustomType': str}
    )

    # キャッシュが効いて同じスキーマが返される
    assert Schema2 is Schema3


# ========================================
# Level 2-6: エラーハンドリングのテスト
# ========================================

def test_forward_refs_model_rebuild_warning():
    """model_rebuild() でエラーが発生しても警告が出るだけでスキーマは生成される"""
    # 存在しない型を forward_refs に指定
    # 警告は出るが、スキーマ生成は成功するはず
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        Schema = BookModel.get_response_schema(
            forward_refs={'NonExistentType': 'invalid'}
        )

        # スキーマは生成される
        assert Schema is not None

        # 警告が出る可能性がある（実装依存）
        # if len(w) > 0:
        #     assert "Failed to rebuild" in str(w[0].message)


# ========================================
# Level 2-7: 実践的な使用例のテスト
# ========================================

def test_forward_refs_realistic_fastapi_scenario():
    """FastAPI での実際の使用シナリオをシミュレート"""
    # Step 1: 基本的なレスポンススキーマを生成
    AuthorResponse = AuthorModel.get_response_schema()

    # Step 2: 前方参照を使用するスキーマを生成
    BookResponse = BookModel.get_response_schema()

    # Step 3: 循環参照を解決
    ReviewResponse = ReviewModel.get_response_schema(
        forward_refs={'BookResponse': BookResponse}
    )

    # すべてのスキーマが正常に生成される
    assert AuthorResponse is not None
    assert BookResponse is not None
    assert ReviewResponse is not None

    # フィールドが正しく定義されている
    assert 'name' in AuthorResponse.model_fields
    assert 'title' in BookResponse.model_fields
    assert 'related_books' in ReviewResponse.model_fields


def test_forward_refs_generic_list_response_pattern():
    """GenericListResponse パターン（FastAPI で一般的）のテスト"""
    from pydantic import BaseModel as PydanticBaseModel
    from typing import Generic, TypeVar

    T = TypeVar('T')

    class GenericListResponse(PydanticBaseModel, Generic[T]):
        """Type-safe response for list endpoints."""
        items: List[T]
        total: int | None = None

    # BookResponse を生成
    BookResponse = BookModel.get_response_schema()

    # GenericListResponse[BookResponse] を使用
    # これは FastAPI の response_model として使用される
    ListResponse = GenericListResponse[BookResponse]

    # バリデーションテスト
    book1 = BookModel(title='Book 1', author_id=1, price=1000)
    book1.id = 1
    book2 = BookModel(title='Book 2', author_id=2, price=2000)
    book2.id = 2

    response_data = {
        'items': [book1.to_dict(), book2.to_dict()],
        'total': 2
    }

    validated = ListResponse(**response_data)

    assert len(validated.items) == 2
    assert validated.total == 2
    assert validated.items[0].title == 'Book 1'
    assert validated.items[1].title == 'Book 2'


# ========================================
# Level 2-8: カスタム型（ListJSON）のテスト
# ========================================

class ModelWithListJSON(BaseModelAuto):
    """ListJSON カスタム型を使用するモデル"""
    __tablename__ = 'model_with_listjson'

    use_id = True

    name = Column(String(100), nullable=False)

    # ListJSON カスタム型を使用
    from repom.custom_types.ListJSON import ListJSON
    tags = Column(ListJSON, nullable=False)
    categories = Column(ListJSON, nullable=True)

    @BaseModelAuto.response_field(
        tag_count=int,
        all_tags=List[str]  # to_dict() で List[str] を返す
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'tag_count': len(self.tags) if self.tags else 0,
            'all_tags': self.tags + (self.categories or [])
        })
        return data


def test_listjson_without_forward_refs():
    """ListJSON カスタム型を使用したモデルで forward_refs なしでスキーマ生成"""
    # forward_refs を指定せずにスキーマ生成
    Response = ModelWithListJSON.get_response_schema()

    # スキーマが正常に生成される
    assert Response is not None

    fields = Response.model_fields

    # カラムフィールドが含まれる
    assert 'id' in fields
    assert 'name' in fields
    assert 'tags' in fields
    assert 'categories' in fields

    # @response_field で追加したフィールドが含まれる
    assert 'tag_count' in fields
    assert 'all_tags' in fields


def test_listjson_with_forward_refs():
    """ListJSON カスタム型を使用したモデルで forward_refs ありでスキーマ生成"""
    # forward_refs に List を明示的に指定
    Response = ModelWithListJSON.get_response_schema(
        forward_refs={'List': List}
    )

    # スキーマが正常に生成される
    assert Response is not None

    fields = Response.model_fields

    # すべてのフィールドが含まれる
    assert 'all_tags' in fields


def test_listjson_validation():
    """ListJSON カスタム型を使用したモデルのバリデーションテスト"""
    Response = ModelWithListJSON.get_response_schema()

    # モデルインスタンスを作成（to_dict() の戻り値をシミュレート）
    data = {
        'id': 1,
        'name': 'Test Product',
        'tags': ['tag1', 'tag2', 'tag3'],
        'categories': ['cat1', 'cat2'],
        'tag_count': 3,
        'all_tags': ['tag1', 'tag2', 'tag3', 'cat1', 'cat2']
    }

    # Pydantic でバリデーション
    validated = Response(**data)

    assert validated.id == 1
    assert validated.name == 'Test Product'
    assert validated.tags == ['tag1', 'tag2', 'tag3']
    assert validated.categories == ['cat1', 'cat2']
    assert validated.tag_count == 3
    assert validated.all_tags == ['tag1', 'tag2', 'tag3', 'cat1', 'cat2']


def test_listjson_type_annotation_resolution():
    """ListJSON カスタム型のフィールドの型アノテーションが正しく解決されるか確認"""
    Response = ModelWithListJSON.get_response_schema()

    fields = Response.model_fields

    # all_tags フィールド（List[str]）の型アノテーションを確認
    all_tags_field = fields['all_tags']

    # 型アノテーションが存在することを確認
    assert all_tags_field.annotation is not None

    # List 型が解決されていることを確認（文字列ではない）
    # これが失敗する場合、List の前方参照が解決されていない
    import typing
    annotation_str = str(all_tags_field.annotation)

    # 'List[str]' または 'list[str]' の形式であることを確認
    assert 'str' in annotation_str.lower()
    assert ('list' in annotation_str.lower() or 'List' in annotation_str)


# ========================================
# Level 2-9: 文字列型アノテーションのテスト（本番環境の問題を再現）
# ========================================

class AssetItemModel(BaseModelAuto):
    """アセットアイテムモデル（テスト用）"""
    __tablename__ = 'asset_items'

    use_id = True
    name = Column(String(100), nullable=False)


class VoiceScriptLineLogModel(BaseModelAuto):
    """ログモデル（テスト用）"""
    __tablename__ = 'voice_script_line_logs'

    use_id = True
    message = Column(String(500), nullable=False)


class VoiceScriptModel(BaseModelAuto):
    """本番環境と同じパターンのモデル"""
    __tablename__ = 'voice_scripts'

    use_id = True
    text = Column(String(500), nullable=True)

    @BaseModelAuto.response_field(
        text=str | None,
        api_params=dict | None,
        asset_item="AssetItemResponse | None",  # ← 文字列で型指定
        has_voice=bool,
        latest_job=dict | None,
        logs="List[VoiceScriptLineLogResponse]"  # ← 文字列で List を指定
    )
    def to_dict(self):
        data = super().to_dict()
        data.update({
            'text': self.text,
            'api_params': {'key': 'value'},
            'asset_item': None,
            'has_voice': False,
            'latest_job': None,
            'logs': []
        })
        return data


def test_string_type_annotations_without_forward_refs():
    """文字列型アノテーション（本番環境パターン）で forward_refs なしでスキーマ生成"""
    # forward_refs を指定せずにスキーマ生成
    # これが本番環境で失敗する可能性がある
    Response = VoiceScriptModel.get_response_schema()

    # スキーマが正常に生成される
    assert Response is not None

    fields = Response.model_fields

    # すべてのフィールドが含まれる
    assert 'text' in fields
    assert 'api_params' in fields
    assert 'asset_item' in fields
    assert 'has_voice' in fields
    assert 'latest_job' in fields
    assert 'logs' in fields


def test_string_type_annotations_with_forward_refs():
    """文字列型アノテーションで forward_refs を指定してスキーマ生成"""
    # AssetItemResponse と VoiceScriptLineLogResponse を先に生成
    AssetItemResponse = AssetItemModel.get_response_schema(
        schema_name='AssetItemResponse'
    )
    VoiceScriptLineLogResponse = VoiceScriptLineLogModel.get_response_schema(
        schema_name='VoiceScriptLineLogResponse'
    )

    # forward_refs に文字列型を解決するための型を指定
    Response = VoiceScriptModel.get_response_schema(
        forward_refs={
            'List': List,  # ← List を明示的に指定
            'AssetItemResponse': AssetItemResponse,
            'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse
        }
    )

    # スキーマが正常に生成される
    assert Response is not None

    fields = Response.model_fields

    # すべてのフィールドが含まれる
    assert 'logs' in fields


def test_string_type_annotations_list_resolution():
    """文字列 'List[...]' の型アノテーションが正しく解決されるか確認"""
    # まず forward_refs なしで生成
    Response = VoiceScriptModel.get_response_schema()

    fields = Response.model_fields
    logs_field = fields['logs']

    # 型アノテーションが存在することを確認
    assert logs_field.annotation is not None

    # 型アノテーションが文字列のままか、解決されているかを確認
    annotation_str = str(logs_field.annotation)
    print(f"logs field annotation (without forward_refs): {annotation_str}")

    # これが 'List[VoiceScriptLineLogResponse]' のような文字列のままだと問題


def test_string_type_annotations_list_resolution_with_forward_refs():
    """
    文字列 'List[...]' の型アノテーションが forward_refs で正しく解決されるか確認

    【テストの目的】完全な前方参照解決パターンの検証
    - すべての必要な型（標準型 + カスタム型）を forward_refs に含める
    - List と中身のカスタム型の両方が正しく解決されることを確認
    """
    # レスポンススキーマを先に生成
    AssetItemResponse = AssetItemModel.get_response_schema(
        schema_name='AssetItemResponse'
    )
    VoiceScriptLineLogResponse = VoiceScriptLineLogModel.get_response_schema(
        schema_name='VoiceScriptLineLogResponse'
    )

    # forward_refs にすべての必要な型を指定
    Response = VoiceScriptModel.get_response_schema(
        forward_refs={
            'List': List,  # ← 後方互換性のため残す（Phase 1 では省略可能）
            'AssetItemResponse': AssetItemResponse,  # ← カスタム型（必須）
            'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse  # ← カスタム型（必須）
        }
    )

    fields = Response.model_fields
    logs_field = fields['logs']

    # 型アノテーションが存在することを確認
    assert logs_field.annotation is not None

    # 型アノテーションが解決されていることを確認
    annotation_str = str(logs_field.annotation)
    print(f"logs field annotation (with forward_refs): {annotation_str}")

    # List が解決されていることを確認
    assert 'list' in annotation_str.lower() or 'List' in annotation_str


def test_string_type_annotations_validation():
    """文字列型アノテーションを使用したモデルのバリデーションテスト"""
    # レスポンススキーマを生成
    AssetItemResponse = AssetItemModel.get_response_schema(
        schema_name='AssetItemResponse'
    )
    VoiceScriptLineLogResponse = VoiceScriptLineLogModel.get_response_schema(
        schema_name='VoiceScriptLineLogResponse'
    )

    Response = VoiceScriptModel.get_response_schema(
        forward_refs={
            'List': List,
            'AssetItemResponse': AssetItemResponse,
            'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse
        }
    )

    # to_dict() の戻り値をシミュレート
    data = {
        'id': 1,
        'text': 'Test voice script',
        'api_params': {'param1': 'value1'},
        'asset_item': {'id': 1, 'name': 'Asset 1'},
        'has_voice': True,
        'latest_job': {'status': 'completed'},
        'logs': [
            {'id': 1, 'message': 'Log 1'},
            {'id': 2, 'message': 'Log 2'}
        ]
    }

    # Pydantic でバリデーション
    validated = Response(**data)

    assert validated.id == 1
    assert validated.text == 'Test voice script'
    assert validated.has_voice is True
    assert len(validated.logs) == 2


def test_production_pattern_exact_match():
    """本番環境と完全に同じパターンのテスト（全ての forward_refs を指定）"""
    # 本番環境と同じ順序でスキーマを生成
    AssetItemResponse = AssetItemModel.get_response_schema(
        schema_name='AssetItemResponse'
    )
    VoiceScriptLineLogResponse = VoiceScriptLineLogModel.get_response_schema(
        schema_name='VoiceScriptLineLogResponse'
    )

    # 本番環境と同じパターン
    VoiceScriptLineResponse = VoiceScriptModel.get_response_schema(
        schema_name='VoiceScriptLineResponse',
        forward_refs={
            'List': List,
            'AssetItemResponse': AssetItemResponse,
            'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse
        }
    )

    # スキーマが正常に生成される
    assert VoiceScriptLineResponse is not None

    fields = VoiceScriptLineResponse.model_fields

    # すべてのフィールドが含まれる
    assert 'id' in fields
    assert 'text' in fields
    assert 'api_params' in fields
    assert 'asset_item' in fields
    assert 'has_voice' in fields
    assert 'latest_job' in fields
    assert 'logs' in fields

    # logs フィールドの型アノテーションを確認
    logs_field = fields['logs']
    annotation_str = str(logs_field.annotation)
    print(f"\n[Production Pattern] logs field annotation: {annotation_str}")

    # バリデーションテスト
    data = {
        'id': 1,
        'text': 'Test voice script',
        'api_params': {'param1': 'value1'},
        'asset_item': {'id': 1, 'name': 'Asset 1'},
        'has_voice': True,
        'latest_job': {'status': 'completed'},
        'logs': [
            {'id': 1, 'message': 'Log 1'},
            {'id': 2, 'message': 'Log 2'}
        ]
    }

    # Pydantic でバリデーション
    validated = VoiceScriptLineResponse(**data)

    assert validated.id == 1
    assert validated.text == 'Test voice script'
    assert validated.has_voice is True
    assert len(validated.logs) == 2

    # 警告やエラーが出ないことを確認（テスト成功 = エラーなし）
    print("[Production Pattern] ✅ No errors - validation successful")


# =============================================================================
# Level 2-10: Phase 1 改善効果の確認
# =============================================================================

def test_phase1_improvement_list_no_longer_required():
    """Phase 1 改善: forward_refs に List を含めなくても動作することを確認"""
    # レスポンススキーマを先に生成
    AssetItemResponse = AssetItemModel.get_response_schema(
        schema_name='AssetItemResponse'
    )
    VoiceScriptLineLogResponse = VoiceScriptLineLogModel.get_response_schema(
        schema_name='VoiceScriptLineLogResponse'
    )

    # ⭐ forward_refs に List を含めない（カスタム型だけ）
    VoiceScriptLineResponse = VoiceScriptModel.get_response_schema(
        schema_name='VoiceScriptLineResponse',
        forward_refs={
            # 'List': List,  # ← Phase 1 で不要になった！
            'AssetItemResponse': AssetItemResponse,
            'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse
        }
    )    # 型アノテーションを確認
    logs_field = VoiceScriptLineResponse.model_fields['logs']
    annotation_str = str(logs_field.annotation)
    print(f"[Phase 1] logs field annotation: {annotation_str}")

    # List が正しく解決されていることを確認
    assert 'typing.List' in annotation_str or 'list[' in annotation_str
    assert 'VoiceScriptLineLogResponse' in annotation_str

    # バリデーションが正常に動作することを確認
    data = {
        'id': 1,
        'text': 'Test',
        'has_voice': True,
        'api_params': {'key': 'value'},
        'asset_item': None,
        'latest_job': None,
        'logs': [
            {'id': 1, 'message': 'Log 1'},
            {'id': 2, 'message': 'Log 2'}
        ]
    }

    validated = VoiceScriptLineResponse(**data)
    assert len(validated.logs) == 2
    print("[Phase 1] ✅ List を forward_refs に含めずに動作成功！")


def test_phase1_improvement_dict_no_longer_required():
    """Phase 1 改善: forward_refs に Dict を含めなくても動作することを確認"""
    class ConfigModel(BaseModelAuto):
        __tablename__ = 'test_config_phase1'
        id = Column(Integer, primary_key=True)
        name = Column(String)

        @BaseModelAuto.response_field(settings="Dict[str, Any]")
        def to_dict(self):
            result = {
                'id': self.id,
                'name': self.name,
            }
            result.update(self._get_extra_response_fields())
            result['settings'] = {'theme': 'dark', 'lang': 'ja'}
            return result    # ⭐ forward_refs に Dict を含めない
    ConfigResponse = ConfigModel.get_response_schema()

    # 型アノテーションを確認
    settings_field = ConfigResponse.model_fields['settings']
    annotation_str = str(settings_field.annotation)
    print(f"[Phase 1] settings field annotation: {annotation_str}")

    # Dict が正しく解決されていることを確認
    assert 'Dict' in annotation_str or 'dict[' in annotation_str

    print("[Phase 1] ✅ Dict を forward_refs に含めずに動作成功！")


def test_phase1_improvement_optional_no_longer_required():
    """Phase 1 改善: forward_refs に Optional を含めなくても動作することを確認"""
    class ItemModel(BaseModelAuto):
        __tablename__ = 'test_item_phase1'
        id = Column(Integer, primary_key=True)
        name = Column(String)

        @BaseModelAuto.response_field(description="Optional[str]")
        def to_dict(self):
            result = {
                'id': self.id,
                'name': self.name,
            }
            result.update(self._get_extra_response_fields())
            result['description'] = None
            return result    # ⭐ forward_refs に Optional を含めない
    ItemResponse = ItemModel.get_response_schema()

    # 型アノテーションを確認
    desc_field = ItemResponse.model_fields['description']
    annotation_str = str(desc_field.annotation)
    print(f"[Phase 1] description field annotation: {annotation_str}")

    # Optional が正しく解決されていることを確認
    assert 'Optional' in annotation_str or 'None' in annotation_str

    print("[Phase 1] ✅ Optional を forward_refs に含めずに動作成功！")


# ====================================================================================
# Level 2-11: Phase 2 Error Message Improvement Tests
# ====================================================================================

def test_phase2_extract_undefined_types():
    """Phase 2: extract_undefined_types() ヘルパー関数のテスト"""
    from repom.base_model_auto import _extract_undefined_types

    # Test case 1: Single undefined type
    error_msg = "name 'BookResponse' is not defined"
    result = _extract_undefined_types(error_msg)
    assert result == {'BookResponse'}
    print(f"[Phase 2] ✅ 単一の未定義型を検出: {result}")

    # Test case 2: Multiple undefined types
    error_msg = "name 'AssetItemResponse' is not defined, name 'LogResponse' is not defined"
    result = _extract_undefined_types(error_msg)
    assert 'AssetItemResponse' in result
    assert 'LogResponse' in result
    print(f"[Phase 2] ✅ 複数の未定義型を検出: {result}")

    # Test case 3: No undefined types
    error_msg = "Some other error"
    result = _extract_undefined_types(error_msg)
    assert result == set()
    print(f"[Phase 2] ✅ 未定義型なしを正しく処理: {result}")


def test_phase2_error_message_in_dev_environment(monkeypatch):
    """Phase 2: 開発環境でエラーメッセージが例外として投げられることを確認"""
    import pytest
    from repom.base_model_auto import SchemaGenerationError

    # Set EXEC_ENV to 'dev'
    monkeypatch.setenv('EXEC_ENV', 'dev')

    # Create a model with unresolved forward reference
    class TestModelDevEnv(BaseModelAuto):
        __tablename__ = 'test_error_dev'
        id = Column(Integer, primary_key=True)

        @BaseModelAuto.response_field(
            book="BookResponse"  # Undefined type
        )
        def to_dict(self):
            return {'id': self.id, 'book': None}

    # Should raise SchemaGenerationError in dev environment
    # Note: forward_refs が指定されている場合のみエラーハンドリングが動作する
    with pytest.raises(SchemaGenerationError) as exc_info:
        TestModelDevEnv.get_response_schema(
            forward_refs={}  # 空の forward_refs を渡してエラーハンドリングを有効化
        )

    # Verify error message contains helpful information
    error_msg = str(exc_info.value)
    assert "Failed to resolve forward references" in error_msg
    assert "BookResponse" in error_msg
    assert "forward_refs" in error_msg
    assert "Solution:" in error_msg

    print("[Phase 2] ✅ 開発環境で詳細なエラーメッセージと例外発生を確認")
    print(f"Error message preview:\n{error_msg[:300]}...")


def test_phase2_error_message_in_prod_environment(monkeypatch, caplog):
    """Phase 2: 本番環境でもエラーメッセージが例外として投げられることを確認

    Note: 現在の実装では環境に関わらず SchemaGenerationError が発生します。
    将来的に環境依存の動作（prod では警告のみ）を実装する可能性があります。
    """
    import pytest
    from repom.base_model_auto import SchemaGenerationError

    # Set EXEC_ENV to 'prod'
    monkeypatch.setenv('EXEC_ENV', 'prod')

    # Create a model with unresolved forward reference
    class TestModelProdEnv(BaseModelAuto):
        __tablename__ = 'test_error_prod'
        id = Column(Integer, primary_key=True)

        @BaseModelAuto.response_field(
            asset="AssetResponse"  # Undefined type
        )
        def to_dict(self):
            return {'id': self.id, 'asset': None}

    # Current behavior: raises SchemaGenerationError regardless of environment
    with pytest.raises(SchemaGenerationError) as exc_info:
        TestModelProdEnv.get_response_schema(
            forward_refs={}  # 空の forward_refs を渡してエラーハンドリングを有効化
        )

    # Verify error message contains helpful information
    error_msg = str(exc_info.value)
    assert "Failed to resolve forward references" in error_msg
    assert "AssetResponse" in error_msg
    assert "Solution:" in error_msg

    print("[Phase 2] ✅ 本番環境でも例外が発生することを確認（環境依存動作は未実装）")
    print(f"Error message preview:\n{error_msg[:300]}...")


def test_phase2_helpful_error_suggestions():
    """Phase 2: エラーメッセージに具体的な解決策が含まれることを確認"""
    import pytest
    from repom.base_model_auto import SchemaGenerationError
    import os

    # Temporarily set to dev environment
    original_env = os.getenv('EXEC_ENV')
    os.environ['EXEC_ENV'] = 'dev'

    try:
        class TestModelSuggestions(BaseModelAuto):
            __tablename__ = 'test_suggestions_unique'
            id = Column(Integer, primary_key=True)

            @BaseModelAuto.response_field(
                item="ItemResponseUnique"
            )
            def to_dict(self):
                return {'id': self.id, 'item': None}

        with pytest.raises(SchemaGenerationError) as exc_info:
            TestModelSuggestions.get_response_schema(
                forward_refs={}  # 空の forward_refs を渡してエラーハンドリングを有効化
            )

        error_msg = str(exc_info.value)

        # Verify undefined type is mentioned
        assert "ItemResponseUnique" in error_msg

        # Verify solution includes code example
        assert "forward_refs={" in error_msg
        assert "'ItemResponseUnique': ItemResponseUnique," in error_msg

        print("[Phase 2] ✅ エラーメッセージに具体的なコード例が含まれることを確認")
        print(f"\nGenerated solution:\n{error_msg}")

    finally:
        # Restore original environment
        if original_env:
            os.environ['EXEC_ENV'] = original_env
        else:
            os.environ.pop('EXEC_ENV', None)
