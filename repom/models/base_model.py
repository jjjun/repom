import json
import uuid
from sqlalchemy import Integer, String, event, inspect
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import TYPE_CHECKING
from repom.database import Base
from repom.custom_types.AutoDateTime import AutoDateTime

# センチネル値（パラメータが指定されていないことを示す）
_UNSET = object()


class BaseModel(Base):
    """
    モデルの基底クラス
    """

    # このクラスは抽象基底クラスとして定義する際に abstract=True を指定する
    __abstract__ = True

    def __init_subclass__(
        cls,
        use_id=_UNSET,
        use_uuid=_UNSET,
        use_created_at=_UNSET,
        use_updated_at=_UNSET,
        **kwargs
    ):
        """
        サブクラス作成時に呼ばれる。

        クラス定義時にパラメータまたはクラス属性で指定することで、デフォルト値を制御できます。

        パラメータ方式（推奨）:
            class MyModel(BaseModel, use_id=False, use_created_at=True):
                __tablename__ = 'my_table'
                ...

        クラス属性方式（従来の方法）:
            class MyModel(BaseModel):
                __tablename__ = 'my_table'
                use_id = False
                use_created_at = True
                ...

        デフォルト値:
        - use_id: True（自動採番の id カラムを追加）
        - use_uuid: False（UUID 主キーを使用しない）
        - use_created_at: False（created_at カラムを追加しない）
        - use_updated_at: False（updated_at カラムを追加しない）

        use_id と use_uuid の関係:
        - use_uuid=True の場合、use_id は自動的に False になります
        - 両方を同時に True にすることはできません
        - use_uuid=True の場合、id カラムは VARCHAR(36) の UUID として作成されます

        複合主キーを使用する場合は use_id=False を指定し、
        各カラムに primary_key=True を設定してください。

        重要:
        - 抽象クラス（__tablename__ がないクラス）にはカラムを追加しません
        - 具象クラス（__tablename__ を持つクラス）のみカラムを追加します
        - これにより、中間の抽象クラスでカラム継承の問題を回避できます
        - パラメータ方式とクラス属性方式の両方がサポートされます
        - パラメータが指定された場合、パラメータが優先されます
        """
        super().__init_subclass__(**kwargs)

        # パラメータが指定されていない場合は親クラスの値を継承、なければデフォルト値を使用
        if use_uuid is _UNSET:
            cls.use_uuid = getattr(cls, 'use_uuid', False)
        else:
            cls.use_uuid = use_uuid

        # use_uuid=True の場合、use_id は自動的に False になる
        if cls.use_uuid:
            if use_id is not _UNSET and use_id:
                # 明示的に use_id=True が指定されている場合はエラー
                raise ValueError(
                    f"{cls.__name__}: use_id と use_uuid は同時に True にできません。"
                    "どちらか一方のみを True に設定してください。"
                )
            cls.use_id = False
        else:
            # use_uuid=False の場合、use_id のデフォルト動作
            if use_id is _UNSET:
                cls.use_id = getattr(cls, 'use_id', True)
            else:
                cls.use_id = use_id

        if use_created_at is _UNSET:
            cls.use_created_at = getattr(cls, 'use_created_at', False)
        else:
            cls.use_created_at = use_created_at

        if use_updated_at is _UNSET:
            cls.use_updated_at = getattr(cls, 'use_updated_at', False)
        else:
            cls.use_updated_at = use_updated_at

        # 重要: 抽象クラス（__tablename__ がない）にはカラムを追加しない
        # 具象クラス（__tablename__ がある）のみカラムを追加する
        # これにより、中間の抽象クラスで use_id=False を指定しても、
        # そのサブクラスで use_id=True を指定できるようになる
        if not hasattr(cls, '__tablename__'):
            # 抽象クラスなので、カラムを追加せずに終了
            return

        # __annotations__ を初期化（親クラスから継承した不要なアノテーションを避ける）
        if '__annotations__' not in cls.__dict__:
            cls.__annotations__ = {}

        # 具象クラスのみ、use_id または use_uuid が True の場合に id カラムを追加
        # SQLAlchemy 2.0 スタイル: mapped_column() + 型ヒント
        if cls.use_uuid:
            # UUID 主キー（VARCHAR 36, ハイフン付き）
            # default は DB レベル、Python レベルでは __init__ で生成
            cls.id: Mapped[str] = mapped_column(
                String(36),
                primary_key=True,
                default=lambda: str(uuid.uuid4())  # DB レベルのデフォルト
            )
            # 動的に追加されたカラムの型ヒントを __annotations__ に登録
            cls.__annotations__['id'] = Mapped[str]

            # __init__ をオーバーライドして UUID を自動生成
            original_init = cls.__init__

            def __init__(self, *args, **kwargs):
                # id が指定されていない場合、UUID を自動生成
                if 'id' not in kwargs:
                    kwargs['id'] = str(uuid.uuid4())
                original_init(self, *args, **kwargs)
            cls.__init__ = __init__

        elif cls.use_id:
            # 自動採番 id（INTEGER）
            cls.id: Mapped[int] = mapped_column(Integer, primary_key=True)
            # 動的に追加されたカラムの型ヒントを __annotations__ に登録
            cls.__annotations__['id'] = Mapped[int]

        if cls.use_created_at:
            cls.created_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)
            # 動的に追加されたカラムの型ヒントを __annotations__ に登録
            cls.__annotations__['created_at'] = Mapped[datetime]

        if cls.use_updated_at:
            cls.updated_at: Mapped[datetime] = mapped_column(AutoDateTime, nullable=False)
            # 動的に追加されたカラムの型ヒントを __annotations__ に登録
            cls.__annotations__['updated_at'] = Mapped[datetime]

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

        重要:
        - 実際のDBカラムのみが更新対象です
        - @property などの読み取り専用属性は自動的に無視されます
        - 辞書に存在しないカラムのキーがあっても問題ありません

        Args:
            data (dict): 更新するデータ。
            exclude_fields (list, optional): 更新を拒否するフィールドのリスト。デフォルトは None。

        Returns:
            bool: 変更があった場合は True、なければ False。
        """
        # 更新を拒否するデフォルトのフィールド（システムカラム）
        # セキュリティ上、これらは常に除外される（exclude_fields で指定しても除外）
        default_exclude_fields = {'id', 'created_at', 'updated_at'}
        # 引数で指定されたフィールドを追加
        if exclude_fields:
            exclude_fields = set(exclude_fields)
        else:
            exclude_fields = set()
        exclude_fields = exclude_fields.union(default_exclude_fields)

        # SQLAlchemy の mapper を使って、実際のDBカラム名のセットを取得
        mapper = inspect(self.__class__)
        column_keys = {col.key for col in mapper.column_attrs}

        updated = False
        for key, value in data.items():
            # 更新を拒否するフィールドをスキップ
            if key in exclude_fields:
                continue
            # 実際のDBカラムでない場合はスキップ（@property などを除外）
            if key not in column_keys:
                continue
            # 値が異なる場合のみ更新
            if getattr(self, key) != value:
                setattr(self, key, value)
                updated = True
        return updated


# SQLAlchemy Event: updated_at の自動更新
@event.listens_for(BaseModel, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    """
    更新前に updated_at を自動設定

    このイベントは全ての BaseModel サブクラスに自動的に適用されます（propagate=True）。
    レコード更新時に updated_at カラムがあれば、現在時刻で自動更新します。

    動作:
    - SQLite を含むすべてのデータベースで動作
    - updated_at カラムを持つモデルのみ対象
    - 更新のたびに自動実行される

    Args:
        mapper: SQLAlchemy mapper
        connection: データベース接続
        target: 更新対象のモデルインスタンス
    """
    if hasattr(target, 'updated_at'):
        target.updated_at = datetime.now()
