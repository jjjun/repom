import json
from typing import Callable, Type, Any, Dict, Optional
from weakref import WeakKeyDictionary
from sqlalchemy import Column, Integer
from mine_db.db import Base, inspect
from mine_db.custom_types.CreatedAt import CreatedAt

# グローバルレジストリ: クラスオブジェクトをキーとして extra response fields を管理
_EXTRA_FIELDS_REGISTRY: WeakKeyDictionary[type, Dict[str, Any]] = WeakKeyDictionary()


class BaseModel(Base):
    """
    モデルの基底クラス
    """

    # このクラスは抽象基底クラスとして定義する際に abstract=True を指定する
    __abstract__ = True

    # デフォルトで id を使用する
    use_id = True
    # デフォルトでは created_at を使用しない
    use_created_at = False
    # デフォルトでは updated_at を使用しない
    use_updated_at = False

    # Pydanticレスポンススキーマのキャッシュ
    _response_schemas: Dict[str, Type[Any]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.use_id:
            cls.id = Column(Integer, primary_key=True)
        if cls.use_created_at:
            cls.created_at = Column(CreatedAt)
        if cls.use_updated_at:
            cls.updated_at = Column(CreatedAt)

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}

    def to_json(self):
        # default=str は datetime などを文字列に変換するため
        return json.dumps(self.to_dict(), default=str)

    def update_from_dict(self, data: dict, exclude_fields: list = None) -> bool:
        """
        モデルのフィールドを辞書データで更新します。
        特定のフィールドは更新を拒否します。
        変更があった場合は True を返します。

        Args:
            data (dict): 更新するデータ。
            exclude_fields (list, optional): 更新を拒否するフィールドのリスト。デフォルトは None。

        Returns:
            bool: 変更があった場合は True、なければ False。
        """
        # 更新を拒否するデフォルトのフィールド
        default_exclude_fields = {'id'}
        # 引数で指定されたフィールドを追加
        if exclude_fields:
            exclude_fields = set(exclude_fields)
        else:
            exclude_fields = set()
        exclude_fields = exclude_fields.union(default_exclude_fields)

        updated = False
        for key, value in data.items():
            # 更新を拒否するフィールドをスキップ
            if key in exclude_fields:
                continue
            # フィールドが存在し、値が異なる場合のみ更新
            if hasattr(self, key) and getattr(self, key) != value:
                setattr(self, key, value)
                updated = True
        return updated

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

            @BaseModel.response_field(
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
        from pydantic import BaseModel as PydanticBaseModel, create_model

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

            # 型を取得（カスタム型の場合はフォールバック）
            try:
                python_type = col.type.python_type
            except NotImplementedError:
                # カスタム型の場合は Any にフォールバック
                from datetime import datetime
                # CreatedAt などのカスタム型は datetime として扱う
                if 'created_at' in col.name or 'updated_at' in col.name:
                    python_type = datetime
                else:
                    python_type = Any

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

        # Pydantic スキーマを動的生成
        from pydantic import ConfigDict

        schema = create_model(
            schema_name,
            __config__=ConfigDict(from_attributes=True),
            **field_definitions
        )

        # 前方参照を解決（文字列型アノテーションを実際の型に変換）
        if forward_refs:
            try:
                schema.model_rebuild(_types_namespace=forward_refs)
            except Exception as e:
                # デバッグ用にエラーを出力
                import warnings
                warnings.warn(f"Failed to rebuild {schema_name}: {e}")
                pass

        # キャッシュに保存
        cls._response_schemas[cache_key] = schema
        return schema

    @classmethod
    def get_extra_fields_debug(cls) -> Dict[str, Any]:
        """
        デバッグ用: このクラスの extra response fields を表示

        Returns:
            Dict[str, Any]: フィールド名と型のマッピング
        """
        return _EXTRA_FIELDS_REGISTRY.get(cls, {})
