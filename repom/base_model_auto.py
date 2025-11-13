"""自動スキーマ生成機能を持つ BaseModel 拡張

このモジュールは、SQLAlchemy の Column 定義から FastAPI の Pydantic スキーマを
自動生成する機能を提供します。

既存の BaseModel を継承し、以下の機能を追加:
- Column の info パラメータからメタデータを読み取り
- get_create_schema(): Create スキーマの自動生成
- get_update_schema(): Update スキーマの自動生成

使用例:
    class FinRecurringPaymentModel(BaseModelAuto):
        name = Column(
            String(200), 
            nullable=False, 
            unique=True,
            info={
                'in_create': True,
                'in_update': True,
                'description': '支払い名'
            }
        )
"""

from typing import Type, Any, Optional, Dict, List
from pydantic import BaseModel as PydanticBaseModel, create_model, Field
from repom.base_model import BaseModel
from repom.db import inspect


class BaseModelAuto(BaseModel, use_id=False, use_created_at=False, use_updated_at=False):
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

    注意:
    - BaseModelAuto はデフォルトで use_id=False, use_created_at=False, use_updated_at=False
    - サブクラスで必要に応じて use_id=True などを指定可能
    - 複合主キーの場合は use_id=False のまま、各カラムに primary_key=True を設定する
    """

    __abstract__ = True

    # スキーマキャッシュ
    _create_schemas: Dict[str, Type[Any]] = {}
    _update_schemas: Dict[str, Type[Any]] = {}

    @classmethod
    def _is_foreign_key(cls, col) -> bool:
        """カラムが外部キーかどうかを判定"""
        return len(col.foreign_keys) > 0

    @classmethod
    def _should_exclude_from_schema(cls, col, schema_type: str) -> bool:
        """スキーマから除外すべきかどうかを判定

        Args:
            col: SQLAlchemy Column
            schema_type: 'create' or 'update'

        Returns:
            True: 除外する, False: 含める
        """
        # info メタデータを取得
        info = col.info or {}

        # 明示的に指定されている場合はそれに従う
        info_key = f'in_{schema_type}'
        if info_key in info:
            return not info[info_key]

        # システムカラムは除外
        if col.name in {'id', 'created_at', 'updated_at'}:
            return True

        # 外部キーは除外
        if cls._is_foreign_key(col):
            return True

        # それ以外は含める
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
