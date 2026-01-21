import json
from sqlalchemy.types import TypeDecorator, TEXT
from typing import Any, Optional, Union


class JSONEncoded(TypeDecorator):
    """
    Custom SQLAlchemy type to automatically encode and decode JSON data stored in a TEXT column.

    ⚠️ Deprecated: prefer using ``sqlalchemy.JSON`` for new models. 既存コードの後方互換性のために残しています。

    次の仕様に沿う
    - 代入時にDictやListをJSON形式に変換して保存する事を保証
    - 取得時にはDictやListになっている事を保証
    - 2000文字以上のデータも保存できる事
    """

    impl = TEXT
    cache_ok = True  # SQLAlchemy 2.0+ でキャッシュを有効化

    def process_bind_param(self, value: Optional[Union[dict, list]], dialect: Any) -> Optional[str]:
        """
        Encode Python dictionary or list to JSON string before storing in the database.

        :param value: The Python dictionary or list to be stored.
        :param dialect: The database dialect in use.
        :return: JSON string representation of the dictionary or list.
        """
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[Any]:
        """
        Decode JSON string from the database to Python dictionary or list.

        :param value: The JSON string retrieved from the database.
        :param dialect: The database dialect in use.
        :return: Python dictionary or list representation of the JSON string.
        """
        if value is not None:
            value = json.loads(value)
        return value
