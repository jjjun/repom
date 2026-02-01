"""Runtime configuration helpers for :mod:`repom`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Set

from repom._.config_hook import Config, get_config_from_hook


@dataclass
class RepomConfig(Config):
    package_name: str = field(default="repom", init=False)

    # モデル自動インポート設定
    model_locations: List[str] = field(default_factory=list, init=False, repr=False)
    model_excluded_dirs: Set[str] = field(default_factory=set, init=False, repr=False)
    allowed_package_prefixes: Set[str] = field(default_factory=lambda: {'repom.'}, init=False, repr=False)
    model_import_strict: bool = field(default=False, init=False, repr=False)

    # DBの格納ディレクトリ (デフォルトで data_path に入る)
    _db_path: Optional[str] = field(default=None, init=False, repr=False)
    # DBファイル名 デフォルトで exec_env の値により'db.<exec_env>.sqlite' となる
    _db_file: Optional[str] = field(default=None, init=False, repr=False)
    # db接続用の文字列: 'sqlite:///%s/%s' % db_path, db_file の形式
    _db_url: Optional[str] = field(default=None, init=False, repr=False)
    # バックアップ先 - デフォルトで data_path/backups に入る
    _db_backup_path: Optional[str] = field(default=None, init=False, repr=False)
    # マスターデータパス - デフォルトで root_path/data_master
    _master_data_path: Optional[str] = field(default=None, init=False, repr=False)
    # テスト時に in-memory SQLite を使用するか（デフォルト: True）
    _use_in_memory_db_for_tests: bool = field(default=True, init=False, repr=False)
    # SQLAlchemy クエリログ設定
    _enable_sqlalchemy_echo: bool = field(default=False, init=False, repr=False)
    _sqlalchemy_echo_level: str = field(default='INFO', init=False, repr=False)

    # PostgreSQL サポート
    _db_type: Optional[str] = field(default=None, init=False, repr=False)
    _postgres_host: str = field(default='localhost', init=False, repr=False)
    _postgres_port: int = field(default=5432, init=False, repr=False)
    _postgres_user: str = field(default='repom', init=False, repr=False)
    _postgres_password: str = field(default='repom_dev', init=False, repr=False)
    _postgres_db: Optional[str] = field(default=None, init=False, repr=False)

    def init(self):
        """初期化後の処理 - 必要なディレクトリを作成"""
        super().init()  # 親クラスのinitを呼び出し

        if self.auto_create_dirs:
            self._ensure_path_exists([
                self.db_backup_path,
                self.master_data_path
            ])

    @property
    def db_path(self) -> Optional[str]:
        """データベース格納ディレクトリ - デフォルトで data_path"""
        if self._db_path is not None:
            return self._db_path

        return self.data_path

    @db_path.setter
    def db_path(self, value: Optional[str]):
        self._db_path = value

    @property
    def db_file(self) -> Optional[Path]:
        """DBファイル名 - デフォルトで exec_env により 'db.<exec_env>.sqlite' となる"""
        if self._db_file is not None:
            return self._db_file

        if self.exec_env == 'test' or self.exec_env == 'dev':
            filename = 'db.%s.sqlite3' % self.exec_env
        else:
            filename = 'db.sqlite3'

        return filename

    @db_file.setter
    def db_file(self, value: Optional[str]):
        self._db_file = value

    @property
    def db_type(self) -> str:
        """データベースタイプ（sqlite/postgres）
        
        デフォルト: sqlite
        環境変数: DB_TYPE
        
        使用例:
            # 環境変数で指定
            DB_TYPE=postgres poetry run alembic upgrade head
            
            # コードで指定
            config.db_type = 'postgres'
        """
        if self._db_type is not None:
            return self._db_type
        
        import os
        return os.getenv('DB_TYPE', 'sqlite')
    
    @db_type.setter
    def db_type(self, value: str):
        if value not in ('sqlite', 'postgres'):
            raise ValueError(f"Invalid DB_TYPE: {value}. Must be 'sqlite' or 'postgres'.")
        self._db_type = value

    @property
    def postgres_host(self) -> str:
        """PostgreSQL ホスト名
        
        デフォルト: localhost
        環境変数: POSTGRES_HOST
        """
        import os
        return os.getenv('POSTGRES_HOST', self._postgres_host)
    
    @postgres_host.setter
    def postgres_host(self, value: str):
        self._postgres_host = value
    
    @property
    def postgres_port(self) -> int:
        """PostgreSQL ポート番号
        
        デフォルト: 5432
        環境変数: POSTGRES_PORT
        """
        import os
        return int(os.getenv('POSTGRES_PORT', self._postgres_port))
    
    @postgres_port.setter
    def postgres_port(self, value: int):
        self._postgres_port = value
    
    @property
    def postgres_user(self) -> str:
        """PostgreSQL ユーザー名
        
        デフォルト: repom
        環境変数: POSTGRES_USER
        """
        import os
        return os.getenv('POSTGRES_USER', self._postgres_user)
    
    @postgres_user.setter
    def postgres_user(self, value: str):
        self._postgres_user = value
    
    @property
    def postgres_password(self) -> str:
        """PostgreSQL パスワード
        
        デフォルト: repom_dev
        環境変数: POSTGRES_PASSWORD
        """
        import os
        return os.getenv('POSTGRES_PASSWORD', self._postgres_password)
    
    @postgres_password.setter
    def postgres_password(self, value: str):
        self._postgres_password = value
    
    @property
    def postgres_db(self) -> str:
        """PostgreSQL データベース名（環境別）
        
        デフォルト: repom
        環境変数: POSTGRES_DB（ベース名）
        
        exec_env により自動的にサフィックスが追加されます:
        - dev: {base}_dev
        - test: {base}_test
        - prod: {base}
        
        使用例:
            # デフォルト（POSTGRES_DB 未設定時）
            dev  => repom_dev
            test => repom_test
            prod => repom
            
            # POSTGRES_DB=mine_py の場合
            dev  => mine_py_dev
            test => mine_py_test
            prod => mine_py
        """
        if self._postgres_db is not None:
            return self._postgres_db
        
        import os
        base = os.getenv('POSTGRES_DB', 'repom')
        env = self.exec_env
        
        if env == 'test':
            return f"{base}_test"
        elif env == 'dev':
            return f"{base}_dev"
        elif env == 'prod':
            return base
        else:
            return f"{base}_dev"
    
    @postgres_db.setter
    def postgres_db(self, value: str):
        self._postgres_db = value

    @property
    def db_file_path(self) -> Optional[Path]:
        """dbファイルのフルパス(ファイル名含む)"""
        return str(Path(self.db_path) / self.db_file)

    @property
    def db_url(self) -> Optional[str]:
        """データベースURL（SQLite/PostgreSQL 自動切り替え）

        DB_TYPE 環境変数または db_type プロパティにより自動的に切り替わります:
        
        PostgreSQL (DB_TYPE=postgres):
            postgresql+psycopg://user:password@host:port/database
        
        SQLite (DB_TYPE=sqlite, デフォルト):
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
            # PostgreSQL を使用
            DB_TYPE=postgres poetry run alembic upgrade head
            
            # SQLite を使用（デフォルト）
            poetry run alembic upgrade head
        """
        if self._db_url is not None:
            return self._db_url
        
        # PostgreSQL
        if self.db_type == 'postgres':
            return (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        
        # SQLite: テスト環境では in-memory をデフォルトに
        if self.exec_env == 'test' and self.use_in_memory_db_for_tests:
            return 'sqlite:///:memory:'

        # SQLite: 通常環境ではファイルベース
        if self.db_file:
            return f'sqlite:///{self.db_path}/{self.db_file}'
        return None

    @db_url.setter
    def db_url(self, value: Optional[str]):
        self._db_url = value

    @property
    def db_backup_path(self) -> Optional[str]:
        """バックアップディレクトリ - デフォルトで data_path/backups"""
        if self._db_backup_path is not None:
            return self._db_backup_path
        if self.data_path:
            return str(Path(self.data_path) / 'backups')
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
            return str(Path(self.root_path) / 'data_master')
        return None

    @master_data_path.setter
    def master_data_path(self, value: Optional[str]):
        self._master_data_path = value

    @property
    def use_in_memory_db_for_tests(self) -> bool:
        """テスト時に in-memory SQLite を使用するか

        デフォルト: True

        True の場合:
            - exec_env == 'test' 時に自動的に sqlite:///:memory: を使用
            - テストが高速（35倍速）
            - "database is locked" エラーを回避

        False の場合:
            - ファイルベース SQLite を使用（db.test.sqlite3）
            - ファイルベース特有の動作をテストしたい場合に使用

        使用例:
            # config_hook.py でファイルベースに変更
            def get_repom_config():
                config = RepomConfig()
                config.use_in_memory_db_for_tests = False
                return config
        """
        return self._use_in_memory_db_for_tests

    @use_in_memory_db_for_tests.setter
    def use_in_memory_db_for_tests(self, value: bool):
        self._use_in_memory_db_for_tests = value

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

        使用例（外部プロジェクトで有効化）:
            # mine-py/src/mine_py/config.py
            class MinePyConfig(RepomConfig):
                def __init__(self):
                    super().__init__()
                    # 開発環境でのみ有効化
                    if self.exec_env == 'dev':
                        self._enable_sqlalchemy_echo = True

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
        if value not in ('INFO', 'DEBUG'):
            raise ValueError(f"Invalid log level: {value}. Must be 'INFO' or 'DEBUG'.")
        self._sqlalchemy_echo_level = value

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
        if self.db_type == 'postgres':
            return {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True,
            }
        
        # SQLite :memory: DB の場合は、StaticPool を使用して単一接続を全スレッドで共有
        is_memory_db = self.db_url and ':memory:' in self.db_url

        if is_memory_db:
            # :memory: DB 用の設定（StaticPool を使用）
            from sqlalchemy.pool import StaticPool

            kwargs = {
                'poolclass': StaticPool,  # 単一接続を全スレッドで共有
                'connect_args': {'check_same_thread': False},  # スレッド安全性チェックを無効化
            }
        else:
            # ファイルベース SQLite 用の完全な設定
            kwargs = {
                'pool_size': 10,          # 接続プール数
                'max_overflow': 20,       # 最大オーバーフロー接続数
                'pool_timeout': 30,       # 接続待機タイムアウト（秒）
                'pool_recycle': 3600,     # 接続の再利用時間（秒）
                'pool_pre_ping': True,    # 接続前のpingチェック
            }

            # SQLite ファイルベースの場合は check_same_thread を無効化
            if self.db_url and self.db_url.startswith('sqlite'):
                kwargs['connect_args'] = {'check_same_thread': False}

        return kwargs


def hook_config(config: dataclass) -> dataclass:
    """設定フック関数
    """
    root_path = Path(__file__).parent.parent

    config.root_path = str(root_path)

    # モデルの自動登録設定
    config.model_locations = ['repom.examples.models']
    config.allowed_package_prefixes = {'repom.'}

    return config


config = RepomConfig()

config.root_path = str(Path(__file__).parent.parent)

# hook
config = get_config_from_hook(config)

config.init()
