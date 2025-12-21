"""Runtime configuration helpers for :mod:`repom`."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Set

from pathlib import Path
try:
    from _.config_hook import load_hook_function, get_config_from_hook, Config
except ImportError:
    from repom.config_hook import load_hook_function, get_config_from_hook, Config
from dataclasses import dataclass, field


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
    def db_file_path(self) -> Optional[Path]:
        """dbファイルのフルパス(ファイル名含む)"""
        return str(Path(self.db_path) / self.db_file)

    @property
    def db_url(self) -> Optional[str]:
        """データベースURL - 'sqlite:///%s/%s' % db_path, db_file の形式

        テスト環境 (exec_env == 'test') かつ use_in_memory_db_for_tests == True の場合、
        自動的に in-memory SQLite を使用します。

        Benefits of in-memory SQLite for tests:
        - 35x faster (no file I/O)
        - No "database is locked" errors
        - Automatic cleanup after tests
        - Better for sync/async mixed environments
        """
        if self._db_url is not None:
            return self._db_url

        # テスト環境では in-memory SQLite をデフォルトに
        if self.exec_env == 'test' and self.use_in_memory_db_for_tests:
            return 'sqlite:///:memory:'

        # 通常環境ではファイルベース
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
    def engine_kwargs(self) -> dict:
        """create_engine に渡す追加パラメータ

        SQLite/PostgreSQL/MySQL などすべてのデータベースで有効なパラメータを設定。
        外部プロジェクトでオーバーライド可能。

        接続プール設定:
        - pool_size: 接続プールに保持する接続数（デフォルト: 10）
        - max_overflow: pool_size を超えて作成可能な追加接続数（デフォルト: 20）
        - pool_timeout: 接続待機タイムアウト秒数（デフォルト: 30）
        - pool_recycle: 接続の再利用時間秒数（デフォルト: 3600）
        - pool_pre_ping: 接続前のpingチェック（デフォルト: True）

        Returns:
            dict: create_engine に渡すキーワード引数

        使用例（外部プロジェクトでオーバーライド）:
            class MinePyConfig(RepomConfig):
                @property
                def engine_kwargs(self) -> dict:
                    base = super().engine_kwargs
                    base.update({
                        'pool_size': 20,      # 接続数を増やす
                        'max_overflow': 40,
                    })
                    return base
        """
        kwargs = {
            'pool_size': 10,          # 接続プール数
            'max_overflow': 20,       # 最大オーバーフロー接続数
            'pool_timeout': 30,       # 接続待機タイムアウト（秒）
            'pool_recycle': 3600,     # 接続の再利用時間（秒）
            'pool_pre_ping': True,    # 接続前のpingチェック
        }

        # SQLite 固有の設定
        if self.db_url and self.db_url.startswith('sqlite'):
            kwargs['connect_args'] = {'check_same_thread': False}

        return kwargs


config = RepomConfig()

config.root_path = str(Path(__file__).parent.parent)

# hook
config = get_config_from_hook(config)

config.init()
