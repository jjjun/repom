"""自動スキーマ生成機能を持つ BaseModel 拡張

このモジュールは、SQLAlchemy の mapped_column 定義から FastAPI の Pydantic スキーマを
自動生成する機能を提供します。

既存の BaseModel を継承し、以下の機能を追加:
- mapped_column の info パラメータからメタデータを読み取り
- get_create_schema(): Create スキーマの自動生成
- get_update_schema(): Update スキーマの自動生成
- get_response_schema(): Response スキーマの自動生成

使用例:
    from sqlalchemy.orm import Mapped, mapped_column
    
    class FinRecurringPaymentModel(BaseModelAuto):
        name: Mapped[str] = mapped_column(
            String(200), 
            nullable=False, 
            unique=True,
            info={
                'in_create': True,
                'in_update': True,
                'in_response': True,  # Response スキーマにも含める
                'description': '支払い名'
            }
        )
"""

from enum import Enum as PyEnum
from typing import Type, Any, Optional, Dict, List, Callable, Set, Literal
from weakref import WeakKeyDictionary
from pydantic import BaseModel as PydanticBaseModel, create_model, Field
from repom.models.base_model import BaseModel
from sqlalchemy import Enum as SQLAlchemyEnum, inspect
import re
import logging

# グローバルレジストリ: クラスオブジェクトをキーとして extra response fields を管理
_EXTRA_FIELDS_REGISTRY: WeakKeyDictionary[type, Dict[str, Any]] = WeakKeyDictionary()

# Logger
logger = logging.getLogger(__name__)


class SchemaGenerationError(Exception):
    """Raised when schema generation fails due to unresolved forward references"""
    pass


def _extract_undefined_types(error_message: str) -> Set[str]:
    """
    Extract undefined type names from Pydantic error messages.

    Args:
        error_message: The exception message from model_rebuild()

    Returns:
        Set of undefined type names

    Examples:
        >>> _extract_undefined_types("name 'BookResponse' is not defined")
        {'BookResponse'}
        >>> _extract_undefined_types("name 'AssetItemResponse' is not defined")
        {'AssetItemResponse'}
    """
    # Match pattern: name 'TypeName' is not defined
    pattern = r"name '([^']+)' is not defined"
    matches = re.findall(pattern, error_message)
    return set(matches)


class BaseModelAuto(BaseModel):
    """自動スキーマ生成機能を持つ BaseModel 拡張

    mapped_column の info パラメータに以下のキーを指定することで、
    スキーマ生成をコントロールできます:

    - in_create (bool): Create スキーマに含めるか (default: auto)
    - in_update (bool): Update スキーマに含めるか (default: auto)
    - description (str): フィールドの説明

    デフォルトの除外ルール（Create/Update スキーマ）:
    - システムカラム: id, created_at, updated_at（自動生成・自動更新のため）
    - 明示的除外: info={'in_create': False} または info={'in_update': False}

    外部キーの扱い:
    - デフォルトで含まれる（ユーザーが設定可能にするため）
    - センシティブな外部キーは info={'in_create': False} で除外可能

    使用例:
        from sqlalchemy.orm import Mapped, mapped_column

        # 通常モデル（id カラムあり、デフォルト）
        class User(BaseModelAuto):
            __tablename__ = 'users'
            name: Mapped[str] = mapped_column(String(100), info={'in_create': True, 'in_update': True})

        # 複合主キーモデル（id カラムなし）
        class OrderItem(BaseModelAuto, use_id=False):
            __tablename__ = 'order_items'
            order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
            product_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    注意:
    - BaseModelAuto は抽象クラスなので、カラム継承の問題は発生しません
    - サブクラスで use_id=False を指定すれば、id カラムは追加されません
    """
    __abstract__ = True

    # スキーマキャッシュ
    _create_schemas: WeakKeyDictionary[type, Dict[tuple[Any, ...], Type[Any]]] = WeakKeyDictionary()
    _update_schemas: WeakKeyDictionary[type, Dict[tuple[Any, ...], Type[Any]]] = WeakKeyDictionary()
    _response_schemas: WeakKeyDictionary[type, Dict[tuple[Any, ...], Type[Any]]] = WeakKeyDictionary()

    @classmethod
    def _get_schema_cache(
        cls,
        cache: WeakKeyDictionary[type, Dict[tuple[Any, ...], Type[Any]]]
    ) -> Dict[tuple[Any, ...], Type[Any]]:
        if cls not in cache:
            cache[cls] = {}
        return cache[cls]

    @staticmethod
    def _exclude_fields_cache_key(exclude_fields: Optional[List[str]]) -> tuple[str, ...]:
        return tuple(sorted(set(exclude_fields or [])))

    @classmethod
    def _build_schema(
        cls,
        schema_type: str,
        schema_name: str,
        validator_mixin: Type,
        exclude_fields: Optional[List[str]],
        field_builder: Callable[[Any, Dict, Type, Dict], tuple[Any, Any]],
    ) -> Type[PydanticBaseModel]:
        exclude_fields_key = cls._exclude_fields_cache_key(exclude_fields)
        cache_key = (schema_name, validator_mixin, exclude_fields_key)
        cache_by_type = {
            'create': cls._create_schemas,
            'update': cls._update_schemas,
        }
        schema_cache = cls._get_schema_cache(cache_by_type[schema_type])

        if cache_key in schema_cache:
            return schema_cache[cache_key]

        excluded_field_names = set(exclude_fields_key)
        field_definitions = {}

        for column in inspect(cls).mapper.column_attrs:
            col = column.columns[0]

            if col.name in excluded_field_names:
                continue

            if cls._should_exclude_from_schema(col, schema_type):
                continue

            info = col.info or {}
            python_type = cls._get_python_type(col)
            field_kwargs = cls._build_field_kwargs(col, info)
            field_definitions[col.name] = field_builder(
                col,
                info,
                python_type,
                field_kwargs,
            )

        if validator_mixin:
            schema = create_model(
                schema_name,
                __base__=(PydanticBaseModel, validator_mixin),
                **field_definitions
            )
        else:
            schema = create_model(
                schema_name,
                **field_definitions
            )

        schema_cache[cache_key] = schema
        return schema

    @classmethod
    def response_field(cls, **fields):
        """
        デコレータ: to_dict()で追加されるフィールドを宣言

        このデコレータは、to_dict()メソッドが返すフィールドの型情報を宣言します。
        宣言された型情報は get_response_schema() で Pydantic スキーマ生成に使用されます。

        注意:
        - リレーションシップフィールドの循環参照を避けるため、文字列型アノテーション ('ModelResponse') を使用できます
        - デコレータはメタデータを保存するだけで、to_dict() の実行には影響しません（パフォーマンス影響なし）

        使用例:
            from typing import List, Any

            @BaseModelAuto.response_field(
                is_paid=bool,
                total_amount=int,
                num_cashflows=int,
                fin_hama_cfs=List['FinHamaCFResponse']  # 文字列で前方参照
            )
            def to_dict(self):
                data = super().to_dict()
                data.update({
                    'is_paid': True,
                    'total_amount': 1000,
                    'num_cashflows': 5,
                    'fin_hama_cfs': [cf.to_dict() for cf in self.related_items]
                })
                return data

        Args:
            **fields: フィールド名と型のマッピング

        Returns:
            Callable: デコレートされた to_dict() メソッド
        """
        def decorator(to_dict_method: Callable):
            # メソッドにメタデータを付与
            to_dict_method._response_fields = fields
            return to_dict_method
        return decorator

    @classmethod
    def _should_exclude_from_schema(cls, col, schema_type: str) -> bool:
        """スキーマから除外すべきかどうかを判定

        Args:
            col: SQLAlchemy Column
            schema_type: 'create', 'update', or 'response'

        Returns:
            True: 除外する, False: 含める

        除外ルール:
        - Create/Update: システムカラム（id, created_at, updated_at）を除外
        - Response: info で明示的に除外されたフィールドのみ除外
        - 外部キー: デフォルトで含める（info で明示的に除外可能）
        """
        # info メタデータを取得
        info = col.info or {}

        # 明示的に指定されている場合はそれに従う
        info_key = f'in_{schema_type}'
        if info_key in info:
            return not info[info_key]

        # Response スキーマの場合
        if schema_type == 'response':
            # システムカラムは含める（読み取り可能）
            # 外部キーも含める（読み取り可能）
            # info で明示的に除外されていない限り、全て含める
            return False

        # Create/Update スキーマの場合
        # システムカラムは除外（自動生成/自動更新）
        if col.name in {'id', 'created_at', 'updated_at'}:
            return True

        # 外部キーはデフォルトで含める（柔軟性重視）
        # info={'in_create': False} または info={'in_update': False} で明示的に除外可能
        # すでに info のチェックは上で行われているので、ここでは含める
        return False

    @classmethod
    def get_create_schema(
        cls,
        schema_name: str = None,
        validator_mixin: Type = None,
        exclude_fields: Optional[List[str]] = None
    ) -> Type[PydanticBaseModel]:
        """Generate a Pydantic create schema from SQLAlchemy column metadata."""
        if schema_name is None:
            schema_name = f"{cls.__name__.replace('Model', '')}Create"

        def build_create_field(col, info, python_type, field_kwargs):
            is_required = cls._is_required_for_create(col, info)
            default_value = cls._get_default_value(col)

            if is_required:
                return python_type, Field(**field_kwargs)

            if default_value is not None:
                return (
                    python_type,
                    Field(default=default_value, **field_kwargs)
                )

            if col.server_default is not None:
                return (
                    Optional[python_type],
                    Field(default=None, **field_kwargs)
                )

            return (
                Optional[python_type],
                Field(default=None, **field_kwargs)
            )

        return cls._build_schema(
            'create',
            schema_name,
            validator_mixin,
            exclude_fields,
            build_create_field,
        )

    @classmethod
    def get_update_schema(
        cls,
        schema_name: str = None,
        validator_mixin: Type = None,
        exclude_fields: Optional[List[str]] = None
    ) -> Type[PydanticBaseModel]:
        """Generate a Pydantic update schema from SQLAlchemy column metadata."""
        if schema_name is None:
            schema_name = f"{cls.__name__.replace('Model', '')}Update"

        def build_update_field(col, info, python_type, field_kwargs):
            return (
                Optional[python_type],
                Field(default=None, **field_kwargs)
            )

        return cls._build_schema(
            'update',
            schema_name,
            validator_mixin,
            exclude_fields,
            build_update_field,
        )

    @classmethod
    def _get_python_type(cls, col) -> Type:
        """SQLAlchemy Column から Python 型を取得"""
        if isinstance(col.type, SQLAlchemyEnum):
            enum_class = getattr(col.type, 'enum_class', None)
            if enum_class and issubclass(enum_class, PyEnum):
                enum_values = tuple(member.value for member in enum_class)
                if enum_values:
                    return Literal.__getitem__(enum_values)
        try:
            python_type = col.type.python_type
        except (NotImplementedError, AttributeError):
            # カスタム型の場合
            from datetime import datetime, date

            if 'created_at' in col.name or 'updated_at' in col.name:
                return datetime
            elif hasattr(col.type, '__visit_name__'):
                visit_name = col.type.__visit_name__.lower()
                if 'json' in visit_name or 'list' in visit_name:
                    return list
                elif 'date' in visit_name:
                    return date
                elif 'datetime' in visit_name:
                    return datetime
            return Any

        return python_type

    @classmethod
    def _build_field_kwargs(cls, col, info: Dict) -> Dict:
        """Pydantic Field の kwargs を構築"""
        field_kwargs = {}

        # description
        if 'description' in info:
            field_kwargs['description'] = info['description']

        # max_length (String型の場合)
        if hasattr(col.type, 'length') and col.type.length:
            field_kwargs['max_length'] = col.type.length

        return field_kwargs

    @classmethod
    def _is_required_for_create(cls, col, info: Dict) -> bool:
        """Create スキーマで必須かどうかを判定する"""
        for key in ('create_required', 'required_on_create', 'required'):
            if key in info:
                return bool(info[key])

        if col.default is not None:
            return False

        if col.server_default is not None:
            return False

        if col.nullable:
            return False

        return True

    @classmethod
    def _get_default_value(cls, col):
        """Return a usable client-side column default value, if one exists."""
        if col.default is not None:
            if callable(col.default.arg):
                return None
            return col.default.arg

        return None

    @classmethod
    def get_response_schema(
        cls,
        schema_name: str = None,
        forward_refs: Dict[str, Type[Any]] = None
    ) -> Type[Any]:
        """
        to_dict() の結果から動的に Pydantic レスポンススキーマを生成

        このメソッドは、SQLAlchemy モデルのカラム情報と @response_field デコレータで
        宣言された追加フィールドから、Pydantic スキーマを自動生成します。

        生成されたスキーマは自動的にキャッシュされ、同じ引数での再呼び出しは
        キャッシュから返されます（パフォーマンス最適化）。

        Args:
            schema_name: 生成するスキーマ名（省略時は {ModelName}Response）
            forward_refs: 前方参照を解決するための型マッピング
                例: {'FinHamaCFResponse': FinHamaCFResponse}
                List['FinHamaCFResponse'] のような文字列型参照を解決します

        Returns:
            Type[BaseModel]: 生成された Pydantic スキーマクラス

        使用例:
            # 基本的な使用
            FinHamaCFResponse = FinHamaCFModel.get_response_schema()

            # 前方参照を解決
            FinHamaCFGResponse = FinHamaCFGModel.get_response_schema(
                forward_refs={'FinHamaCFResponse': FinHamaCFResponse}
            )
        """
        # to_dictメソッドから_response_fieldsを読み取り、レジストリに登録
        if cls not in _EXTRA_FIELDS_REGISTRY:
            to_dict_method = getattr(cls, 'to_dict', None)
            if to_dict_method and hasattr(to_dict_method, '_response_fields'):
                _EXTRA_FIELDS_REGISTRY[cls] = to_dict_method._response_fields

        if schema_name is None:
            schema_name = f"{cls.__name__.replace('Model', '')}Response"

        # キャッシュキー（forward_refsも含める）
        forward_refs_key = tuple(sorted(forward_refs.keys())) if forward_refs else ()
        cache_key = (schema_name, forward_refs_key)
        schema_cache = cls._get_schema_cache(cls._response_schemas)

        if cache_key in schema_cache:
            return schema_cache[cache_key]

        # フィールド定義を収集
        field_definitions = {}

        # 1. カラムフィールド（SQLAlchemy から自動取得）
        for column in inspect(cls).mapper.column_attrs:
            col = column.columns[0]

            # 除外チェック（info で明示的に除外されている場合）
            if cls._should_exclude_from_schema(col, 'response'):
                continue

            # Python型を取得
            python_type = cls._get_python_type(col)

            if col.nullable:
                field_definitions[col.name] = (Optional[python_type], None)
            else:
                field_definitions[col.name] = (python_type, ...)

        # 2. to_dict()の追加フィールド（@response_field デコレータから取得）
        # グローバルレジストリから、このクラス専用のフィールドを取得
        extra_fields = _EXTRA_FIELDS_REGISTRY.get(cls, {})
        field_definitions.update({
            name: (field_type, ...)
            for name, field_type in extra_fields.items()
        })

        # Pydantic スキーマを生成
        schema = create_model(schema_name, **field_definitions)

        # 前方参照を解決（forward_refs が指定されている場合）
        if forward_refs is not None:
            try:
                schema.model_rebuild(_types_namespace=forward_refs)
                logger.debug(f"Successfully resolved forward references for {schema_name}")
            except NameError as e:
                # 未定義の型を抽出
                undefined_types = _extract_undefined_types(str(e))

                # エラーメッセージを構築
                error_lines = [
                    f"\nFailed to resolve forward references in {cls.__name__}.get_response_schema():",
                    f"  Undefined types: {', '.join(sorted(undefined_types))}",
                    "",
                    "Solution:",
                    "  Pass the missing types in the forward_refs parameter:",
                    f"  schema = {cls.__name__}.get_response_schema(",
                    "      forward_refs={",
                ]

                for undef_type in sorted(undefined_types):
                    error_lines.append(f"          '{undef_type}': {undef_type},")

                error_lines.extend([
                    "      }",
                    "  )",
                    "",
                    f"Original error: {e}"
                ])

                raise SchemaGenerationError("\n".join(error_lines)) from e

        # キャッシュに保存
        schema_cache[cache_key] = schema
        return schema

    @classmethod
    def get_extra_fields_debug(cls) -> Dict[str, Any]:
        """デバッグ用: 登録されている追加フィールドを取得"""
        return _EXTRA_FIELDS_REGISTRY.get(cls, {})
