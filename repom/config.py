"""Runtime configuration helpers for :mod:`repom`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from basekit.config_hook import Config, get_config_from_hook

from repom.postgres.config import (
    PgAdminConfig as _PgAdminConfig,
)
from repom.postgres.config import (
    PostgresConfig as _PostgresConfig,
)
from repom.redis.config import RedisConfig as _RedisConfig
from repom.sqlite.config import SqliteConfig as _SqliteConfig


@dataclass
class RepomConfig(Config):
    package_name: str = field(default="repom", init=False)

    # モデル自動インポート設定
    model_locations: List[str] = field(default_factory=list, init=False, repr=False)
    model_excluded_dirs: Set[str] = field(default_factory=set, init=False, repr=False)
    allowed_package_prefixes: Set[str] = field(
        default_factory=lambda: {"repom."}, init=False, repr=False
    )
    model_import_strict: bool = field(default=False, init=False, repr=False)

    # データベース設定 (機能別に分離)
    postgres: _PostgresConfig = field(default_factory=_PostgresConfig)
    pgadmin: _PgAdminConfig = field(default_factory=_PgAdminConfig)
    redis: _RedisConfig = field(default_factory=_RedisConfig)
    sqlite: _SqliteConfig = field(default_factory=_SqliteConfig)

    # データベースタイプ選択
    _db_type: Optional[str] = field(default=None, init=False, repr=False)

    # DB名のベース（環境サフィックス付与前）
    _db_name: Optional[str] = field(default=None, init=False, repr=False)

    # db接続用の文字列 (カスタマイズ用)
    _db_url: Optional[str] = field(default=None, init=False, repr=False)

    # バックアップ先 - デフォルトで data_path/backups に入る
    _db_backup_path: Optional[str] = field(default=None, init=False, repr=False)
    # マスターデータパス - デフォルトで root_path/data_master
    _master_data_path: Optional[str] = field(default=None, init=False, repr=False)

    # SQLAlchemy クエリログ設定
    _enable_sqlalchemy_echo: bool = field(default=False, init=False, repr=False)
    _sqlalchemy_echo_level: str = field(default="INFO", init=False, repr=False)

    # SQLAlchemy 接続プール設定
    _db_pool_size: int = field(default=10, init=False, repr=False)
    _db_max_overflow: int = field(default=20, init=False, repr=False)
    _db_pool_timeout: int = field(default=30, init=False, repr=False)
    _db_pool_recycle: int = field(default=3600, init=False, repr=False)
    _db_pool_pre_ping: bool = field(default=True, init=False, repr=False)

    def __post_init__(self):
        """dataclassの初期化後に実行"""
        self.init()

    def init(self):
        """初期化後の処理 - 必要なディレクトリを作成"""
        super().init()  # 親クラスのinitを呼び出し

        self.sqlite.bind(self)

        # SqliteConfig のデフォルト値を設定（data_path が存在する場合のみ）
        if self.data_path and self.sqlite.db_path is None:
            self.sqlite.db_path = self.data_path
        # db_file は property で自動計算されるため、ここでの初期化は不要

        if self.auto_create_dirs:
            self._ensure_path_exists([self.db_backup_path, self.master_data_path])

    @property
    def db_type(self) -> str:
        """データベースタイプ（sqlite/postgres）

        デフォルト: sqlite

        使用例:
            # CONFIG_HOOK で指定
            def get_repom_config():
                config = RepomConfig()
                config.db_type = 'postgres'
                return config

            # コードで指定
            from repom.config import config
            config.db_type = 'postgres'
        """
        if self._db_type is not None:
            return self._db_type

        return "sqlite"

    @db_type.setter
    def db_type(self, value: str):
        if value not in ("sqlite", "postgres"):
            raise ValueError(
                f"Invalid DB_TYPE: {value}. Must be 'sqlite' or 'postgres'."
            )
        self._db_type = value

    @property
    def db_name(self) -> str:
        """DB名のベース（デフォルト: repom）

        PostgreSQL と SQLite の両方で使用されます:
        - PostgreSQL: {db_name}_dev, {db_name}_test, {db_name}
        - SQLite: {db_name}_dev.sqlite3, {db_name}_test.sqlite3, {db_name}.sqlite3

        使用例:
            # CONFIG_HOOK で設定
            def hook_config(config):
                config.db_name = 'mine_py'
                return config

            # 結果:
            # dev  => mine_py_dev (PostgreSQL) / mine_py_dev.sqlite3 (SQLite)
            # test => mine_py_test / mine_py_test.sqlite3
            # prod => mine_py / mine_py.sqlite3
        """
        return self._db_name or "repom"

    @db_name.setter
    def db_name(self, value: str):
        self._db_name = value

    @property
    def postgres_db(self) -> str:
        """PostgreSQL データベース名（環境別）

        デフォルト: repom

        exec_env により自動的にサフィックスが追加されます:
        - dev: {base}_dev
        - test: {base}_test
        - prod: {base}

        使用例:
            # デフォルト
            dev  => repom_dev
            test => repom_test
            prod => repom

            # CONFIG_HOOK でベース名を変更
            config.postgres.database = 'mine_py'
        """
        if self.postgres.database is not None:
            return self.postgres.database

        base = self.db_name
        env = self.exec_env

        if env == "test":
            return f"{base}_test"
        elif env == "dev":
            return f"{base}_dev"
        elif env == "prod":
            return base
        else:
            return f"{base}_dev"

    @property
    def db_url(self) -> Optional[str]:
        """データベースURL（SQLite/PostgreSQL 自動切り替え）

        db_type プロパティにより自動的に切り替わります:

        PostgreSQL (db_type='postgres'):
            postgresql+psycopg://user:password@host:port/database

        SQLite (db_type='sqlite', デフォルト):
            sqlite:///path/to/db.sqlite3
            または
            sqlite:///:memory: （テスト環境）

        テスト環境 (exec_env == 'test') かつ use_in_memory_db_for_tests == True の場合、
        SQLite は自動的に in-memory を使用します。

        Benefits of in-memory SQLite for tests:
        - 35x faster (no file I/O)
        - No "database is locked" errors
        - Automatic cleanup after tests
        - Better for sync/async mixed environments

        使用例:
            # CONFIG_HOOK で PostgreSQL を使用
            def get_repom_config():
                config = RepomConfig()
                config.db_type = 'postgres'
                return config

            # SQLite を使用（デフォルト）
            # 何も設定しない場合は自動的に SQLite
        """
        if self._db_url is not None:
            return self._db_url

        # PostgreSQL
        if self.db_type == "postgres":
            return (
                f"postgresql+psycopg://{self.postgres.user}:{self.postgres.password}"
                f"@{self.postgres.host}:{self.postgres.port}/{self.postgres_db}"
            )

        # SQLite: テスト環境では in-memory をデフォルトにする。
        # ファイルベースが必要な場合は config.sqlite.use_in_memory_for_tests
        # または repom.config_hooks.sqlite の env override helper で切り替える。
        if (
            self.exec_env == "test"
            and self.sqlite.use_in_memory_for_tests
        ):
            return "sqlite:///:memory:"

        # SQLite: 通常環境ではファイルベース
        db_path = self.sqlite.db_path if self.sqlite.db_path else self.data_path
        db_file = self.sqlite.db_file  # property で自動計算される
        if db_file:
            return f"sqlite:///{db_path}/{db_file}"
        return None

    @db_url.setter
    def db_url(self, value: Optional[str]):
        self._db_url = value

    @property
    def db_backup_path(self) -> Optional[str]:
        """バックアップディレクトリ - DB タイプ別にサブディレクトリ作成

        Returns:
            - SQLite: data_path/backups/sqlite
            - PostgreSQL: data_path/backups/postgres
        """
        if self._db_backup_path is not None:
            return self._db_backup_path
        if self.data_path:
            base_backup_path = Path(self.data_path) / "backups"
            return str(base_backup_path / self.db_type)
        return None

    @db_backup_path.setter
    def db_backup_path(self, value: Optional[str]):
        self._db_backup_path = value

    @property
    def master_data_path(self) -> Optional[str]:
        """マスターデータパス - デフォルトで root_path/data_master"""
        if self._master_data_path is not None:
            return self._master_data_path
        if self.root_path:
            return str(Path(self.root_path) / "data_master")
        return None

    @master_data_path.setter
    def master_data_path(self, value: Optional[str]):
        self._master_data_path = value

    @property
    def enable_sqlalchemy_echo(self) -> bool:
        """SQLAlchemy のクエリログを有効化するか

        デフォルト: False

        True の場合:
            - すべての SQL クエリがログに出力される
            - N+1 問題の調査に有効
            - 開発・テスト環境での使用を推奨

        False の場合:
            - SQL クエリはログに出力されない
            - 本番環境での推奨設定

        使用例（CONFIG_HOOK で有効化）:
            # mine-py/config.py
            def hook_config(config):
                if config.exec_env == 'dev':
                    config.enable_sqlalchemy_echo = True
                return config

        使用例（一時的に有効化）:
            from repom.config import config
            config.enable_sqlalchemy_echo = True
            # この後のクエリがログに出力される
        """
        return self._enable_sqlalchemy_echo

    @enable_sqlalchemy_echo.setter
    def enable_sqlalchemy_echo(self, value: bool):
        self._enable_sqlalchemy_echo = value

    @property
    def sqlalchemy_echo_level(self) -> str:
        """SQLAlchemy ログのレベル（INFO/DEBUG）

        デフォルト: INFO

        INFO:
            - SQL文のみを出力
            - 通常の N+1 問題調査に最適
            - 出力例: SELECT user.id, user.name FROM user

        DEBUG:
            - SQL文 + パラメータ + 実行結果の詳細
            - より詳細なデバッグが必要な場合に使用
            - 出力例: SELECT user.id, user.name FROM user WHERE user.id = ? [1]

        使用例:
            config.enable_sqlalchemy_echo = True
            config.sqlalchemy_echo_level = 'DEBUG'  # 詳細ログ
        """
        return self._sqlalchemy_echo_level

    @sqlalchemy_echo_level.setter
    def sqlalchemy_echo_level(self, value: str):
        if value not in ("INFO", "DEBUG"):
            raise ValueError(f"Invalid log level: {value}. Must be 'INFO' or 'DEBUG'.")
        self._sqlalchemy_echo_level = value

    @property
    def db_pool_size(self) -> int:
        """接続プールに保持する接続数（デフォルト: 10, 1 以上）

        engine_kwargs の pool_size に渡される。PostgreSQL とファイルベース
        SQLite の QueuePool で有効。:memory: SQLite（StaticPool）では無視される。

        環境変数 SQLALCHEMY_POOL_SIZE で上書き可能。
        """
        return self._db_pool_size

    @db_pool_size.setter
    def db_pool_size(self, value: int):
        if value <= 0:
            raise ValueError(f"Invalid db_pool_size: {value}. Must be greater than 0.")
        self._db_pool_size = value

    @property
    def db_max_overflow(self) -> int:
        """pool_size を超えて作成可能な追加接続数（デフォルト: 20, 0 以上）

        環境変数 SQLALCHEMY_MAX_OVERFLOW で上書き可能。
        """
        return self._db_max_overflow

    @db_max_overflow.setter
    def db_max_overflow(self, value: int):
        if value < 0:
            raise ValueError(
                f"Invalid db_max_overflow: {value}. Must be greater than or equal to 0."
            )
        self._db_max_overflow = value

    @property
    def db_pool_timeout(self) -> int:
        """接続待機タイムアウト秒数（デフォルト: 30, 0 以上）

        環境変数 SQLALCHEMY_POOL_TIMEOUT で上書き可能。
        """
        return self._db_pool_timeout

    @db_pool_timeout.setter
    def db_pool_timeout(self, value: int):
        if value < 0:
            raise ValueError(
                f"Invalid db_pool_timeout: {value}. Must be greater than or equal to 0."
            )
        self._db_pool_timeout = value

    @property
    def db_pool_recycle(self) -> int:
        """接続の再利用時間秒数（デフォルト: 3600, -1 以上）

        -1 で無効化。環境変数 SQLALCHEMY_POOL_RECYCLE で上書き可能。
        """
        return self._db_pool_recycle

    @db_pool_recycle.setter
    def db_pool_recycle(self, value: int):
        if value < -1:
            raise ValueError(
                f"Invalid db_pool_recycle: {value}. Must be greater than or equal to -1."
            )
        self._db_pool_recycle = value

    @property
    def db_pool_pre_ping(self) -> bool:
        """接続前の ping チェック（デフォルト: True）

        環境変数 SQLALCHEMY_POOL_PRE_PING で上書き可能。
        """
        return self._db_pool_pre_ping

    @db_pool_pre_ping.setter
    def db_pool_pre_ping(self, value: bool):
        self._db_pool_pre_ping = value

    @property
    def engine_kwargs(self) -> dict:
        """create_engine に渡す追加パラメータ（DB種別対応）

        SQLite/PostgreSQL/MySQL などすべてのデータベースで有効なパラメータを設定。
        外部プロジェクトでオーバーライド可能。

        接続プール設定:
        - pool_size: 接続プールに保持する接続数（デフォルト: 10）
          * SQLite ファイルDB: 有効（SQLAlchemy 2.0+ は QueuePool 使用）
          * SQLite :memory: DB: 除外（StaticPool は pool_size 未サポート）
          * PostgreSQL: 有効
        - max_overflow: pool_size を超えて作成可能な追加接続数（デフォルト: 20）
          * SQLite ファイルDB: 有効（QueuePool）
          * SQLite :memory: DB: 除外（StaticPool は max_overflow 未サポート）
          * PostgreSQL: 有効
        - pool_timeout: 接続待機タイムアウト秒数（デフォルト: 30）
          * SQLite ファイルDB: 有効（QueuePool）
          * SQLite :memory: DB: 除外（StaticPool は pool_timeout 未サポート）
          * PostgreSQL: 有効
        - pool_recycle: 接続の再利用時間秒数（デフォルト: 3600）
          * すべてのDBで有効
        - pool_pre_ping: 接続前のpingチェック（デフォルト: True）
          * すべてのDBで有効
        - poolclass: 接続プールクラス
          * SQLite :memory: DB: StaticPool（単一接続をすべてのスレッドで共有）
          * その他: デフォルト（NullPool または QueuePool）

        StaticPool の必要性:
        - :memory: DB は1つの connection でのみデータを保持
        - NullPool（デフォルト）では各スレッドで新しい connection が作成される
        - 別の connection からは :memory: DB のデータが見えない
        - StaticPool により単一 connection を全スレッドで共有することで解決

        PostgreSQL 特有の設定:
        - connect_args は不要（PostgreSQL は自動的にスレッドセーフ）
        - pool_pre_ping=True により、切断された接続を自動検知

        Returns:
            dict: create_engine に渡すキーワード引数

        使用例（外部プロジェクトでオーバーライド）:
            class MinePyConfig(RepomConfig):
                @property
                def engine_kwargs(self) -> dict:
                    base = super().engine_kwargs
                    if self.db_type == 'postgres':
                        base.update({
                            'pool_size': 20,      # 接続数を増やす
                            'max_overflow': 40,
                        })
                    return base

        参考:
        - SQLite と QueuePool: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#threading-pooling-behavior
        - Connection Pooling: https://docs.sqlalchemy.org/en/20/core/pooling.html
        - StaticPool: https://docs.sqlalchemy.org/en/20/core/pooling.html#sqlalchemy.pool.StaticPool
        - PostgreSQL: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
        """
        # PostgreSQL
        if self.db_type == "postgres":
            return {
                "pool_size": self.db_pool_size,
                "max_overflow": self.db_max_overflow,
                "pool_timeout": self.db_pool_timeout,
                "pool_recycle": self.db_pool_recycle,
                "pool_pre_ping": self.db_pool_pre_ping,
            }

        # SQLite :memory: DB の場合は、StaticPool を使用して単一接続を全スレッドで共有
        is_memory_db = self.db_url and ":memory:" in self.db_url

        if is_memory_db:
            # :memory: DB 用の設定（StaticPool を使用）
            from sqlalchemy.pool import StaticPool

            kwargs = {
                "poolclass": StaticPool,  # 単一接続を全スレッドで共有
                "connect_args": {
                    "check_same_thread": False
                },  # スレッド安全性チェックを無効化
            }
        else:
            # ファイルベース SQLite 用の完全な設定
            kwargs = {
                "pool_size": self.db_pool_size,  # 接続プール数
                "max_overflow": self.db_max_overflow,  # 最大オーバーフロー接続数
                "pool_timeout": self.db_pool_timeout,  # 接続待機タイムアウト（秒）
                "pool_recycle": self.db_pool_recycle,  # 接続の再利用時間（秒）
                "pool_pre_ping": self.db_pool_pre_ping,  # 接続前のpingチェック
            }

            # SQLite ファイルベースの場合は check_same_thread を無効化
            if self.db_url and self.db_url.startswith("sqlite"):
                kwargs["connect_args"] = {"check_same_thread": False}

        return kwargs


config = RepomConfig()

config.root_path = str(Path(__file__).parent.parent)

# hook
config = get_config_from_hook(config)

config.init()


__all__ = [
    "RepomConfig",
    "config",
]
