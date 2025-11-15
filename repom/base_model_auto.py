"""自動スキーマ生成機能を持つ BaseModel 拡張

このモジュールは、SQLAlchemy の Column 定義から FastAPI の Pydantic スキーマを
自動生成する機能を提供します。

既存の BaseModel を継承し、以下の機能を追加:
- Column の info パラメータからメタデータを読み取り
- get_create_schema(): Create スキーマの自動生成
- get_update_schema(): Update スキーマの自動生成
- get_response_schema(): Response スキーマの自動生成

使用例:
    class FinRecurringPaymentModel(BaseModelAuto):
        name = Column(
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

from typing import Type, Any, Optional, Dict, List, Callable, Set
from weakref import WeakKeyDictionary
from pydantic import BaseModel as PydanticBaseModel, create_model, Field
from repom.base_model import BaseModel
from repom.db import inspect
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

    Column の info パラメータに以下のキーを指定することで、
    スキーマ生成をコントロールできます:

    - in_create (bool): Create スキーマに含めるか (default: auto)
    - in_update (bool): Update スキーマに含めるか (default: auto)
    - description (str): フィールドの説明

    デフォルトの除外ルール:
    - システムカラム: id, created_at, updated_at
    - 外部キー: *_id (ForeignKey を持つカラム)
    - 明示的除外: info={'in_create': False} または info={'in_update': False}

    使用例:
        # 通常モデル（id カラムあり、デフォルト）
        class User(BaseModelAuto):
            __tablename__ = 'users'
            name = Column(String(100), info={'in_create': True, 'in_update': True})

        # 複合主キーモデル（id カラムなし）
        class OrderItem(BaseModelAuto, use_id=False):
            __tablename__ = 'order_items'
            order_id = Column(Integer, primary_key=True)
            product_id = Column(Integer, primary_key=True)

    注意:
    - BaseModelAuto は抽象クラスなので、カラム継承の問題は発生しません
    - サブクラスで use_id=False を指定すれば、id カラムは追加されません
    """
    __abstract__ = True

    # スキーマキャッシュ
    _create_schemas: Dict[str, Type[Any]] = {}
    _update_schemas: Dict[str, Type[Any]] = {}
    _response_schemas: Dict[str, Type[Any]] = {}

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
    def _is_foreign_key(cls, col) -> bool:
        """カラムが外部キーかどうかを判定"""
        return len(col.foreign_keys) > 0

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
        """Column の info メタデータから Create スキーマを自動生成

        Args:
            schema_name: スキーマ名（省略時は {ModelName}Create）
            validator_mixin: バリデーターMixinクラス（オプション）
            exclude_fields: 除外するフィールド名のリスト

        Returns:
            Pydantic BaseModel クラス

        使用例:
            FinRecurringPaymentCreate = FinRecurringPaymentModel.get_create_schema(
                validator_mixin=FinRecurringPaymentValidatorMixin
            )
        """
        if schema_name is None:
            schema_name = f"{cls.__name__.replace('Model', '')}Create"

        # キャッシュキー
        cache_key = f"{cls.__name__}::{schema_name}"
        if validator_mixin:
            cache_key += f"::{validator_mixin.__name__}"

        if cache_key in cls._create_schemas:
            return cls._create_schemas[cache_key]

        exclude_fields = exclude_fields or []
        exclude_fields = set(exclude_fields)

        field_definitions = {}

        for column in inspect(cls).mapper.column_attrs:
            col = column.columns[0]

            # 手動除外リストをチェック
            if col.name in exclude_fields:
                continue

            # 自動除外ルールをチェック
            if cls._should_exclude_from_schema(col, 'create'):
                continue

            # info メタデータを取得
            info = col.info or {}

            # Python型を取得
            python_type = cls._get_python_type(col)

            # Field パラメータを構築
            field_kwargs = cls._build_field_kwargs(col, info)

            # デフォルト値を決定
            default_value = cls._get_default_value(col, for_create=True)

            # フィールド定義を追加
            if default_value is ...:
                # 必須フィールド
                field_definitions[col.name] = (python_type, Field(**field_kwargs))
            else:
                # オプショナルまたはデフォルト値あり
                if col.nullable and default_value is None:
                    # nullable の場合は Optional
                    field_definitions[col.name] = (
                        Optional[python_type],
                        Field(default=None, **field_kwargs)
                    )
                else:
                    # デフォルト値あり
                    field_definitions[col.name] = (
                        python_type,
                        Field(default=default_value, **field_kwargs)
                    )

        # スキーマ生成
        if validator_mixin:
            # Mixin との多重継承（create_model を使用）
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

        # キャッシュに保存
        cls._create_schemas[cache_key] = schema
        return schema

    @classmethod
    def get_update_schema(
        cls,
        schema_name: str = None,
        validator_mixin: Type = None,
        exclude_fields: Optional[List[str]] = None
    ) -> Type[PydanticBaseModel]:
        """Column の info メタデータから Update スキーマを自動生成

        Update スキーマは全フィールドを Optional にします。

        Args:
            schema_name: スキーマ名（省略時は {ModelName}Update）
            validator_mixin: バリデーターMixinクラス（オプション）
            exclude_fields: 除外するフィールド名のリスト

        Returns:
            Pydantic BaseModel クラス
        """
        if schema_name is None:
            schema_name = f"{cls.__name__.replace('Model', '')}Update"

        # キャッシュキー
        cache_key = f"{cls.__name__}::{schema_name}"
        if validator_mixin:
            cache_key += f"::{validator_mixin.__name__}"

        if cache_key in cls._update_schemas:
            return cls._update_schemas[cache_key]

        exclude_fields = exclude_fields or []
        exclude_fields = set(exclude_fields)

        field_definitions = {}

        for column in inspect(cls).mapper.column_attrs:
            col = column.columns[0]

            # 手動除外リストをチェック
            if col.name in exclude_fields:
                continue

            # 自動除外ルールをチェック
            if cls._should_exclude_from_schema(col, 'update'):
                continue

            # info メタデータを取得
            info = col.info or {}

            # Python型を取得
            python_type = cls._get_python_type(col)

            # Field パラメータを構築
            field_kwargs = cls._build_field_kwargs(col, info)

            # Update では全フィールドを Optional にする
            field_definitions[col.name] = (
                Optional[python_type],
                Field(default=None, **field_kwargs)
            )

        # スキーマ生成
        if validator_mixin:
            # Mixin との多重継承（create_model を使用）
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

        # キャッシュに保存
        cls._update_schemas[cache_key] = schema
        return schema

    @classmethod
    def _get_python_type(cls, col) -> Type:
        """SQLAlchemy Column から Python 型を取得"""
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
    def _get_default_value(cls, col, for_create: bool = True):
        """フィールドのデフォルト値を取得

        Args:
            col: SQLAlchemy Column
            for_create: Create用の場合True、Update用の場合False

        Returns:
            デフォルト値、または ... (必須)
        """
        if not for_create:
            # Update では全て None
            return None

        # Column にデフォルト値がある場合
        if col.default is not None:
            if callable(col.default.arg):
                # callable の場合は実行しない（例: datetime.now）
                # Pydantic の default_factory を使うべきだが、ここでは None を返す
                return None if col.nullable else ...
            else:
                return col.default.arg

        # nullable の場合は None
        if col.nullable:
            return None

        # それ以外は必須
        return ...

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
        from typing import List, Dict, Optional, Set, Tuple, Union

        # to_dictメソッドから_response_fieldsを読み取り、レジストリに登録
        if cls not in _EXTRA_FIELDS_REGISTRY:
            to_dict_method = getattr(cls, 'to_dict', None)
            if to_dict_method and hasattr(to_dict_method, '_response_fields'):
                _EXTRA_FIELDS_REGISTRY[cls] = to_dict_method._response_fields

        if schema_name is None:
            schema_name = f"{cls.__name__.replace('Model', '')}Response"

        # キャッシュキー（forward_refsも含める）
        cache_key = f"{cls.__name__}::{schema_name}"
        if forward_refs:
            cache_key += f"::{','.join(sorted(forward_refs.keys()))}"

        if cache_key in cls._response_schemas:
            return cls._response_schemas[cache_key]

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
                    f"  Pass the missing types in the forward_refs parameter:",
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
        cls._response_schemas[cache_key] = schema
        return schema

    @classmethod
    def get_extra_fields_debug(cls) -> Dict[str, Any]:
        """デバッグ用: 登録されている追加フィールドを取得"""
        return _EXTRA_FIELDS_REGISTRY.get(cls, {})
