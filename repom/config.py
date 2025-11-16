"""Runtime configuration helpers for :mod:`mine_db`."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Set

from pathlib import Path
try:
    from _.config_hook import load_hook_function, get_config_from_hook, Config
except ImportError:
    from repom.config_hook import load_hook_function, get_config_from_hook, Config
from dataclasses import dataclass, field


def load_models() -> None:
    """Import all application models so ``mine_db`` can discover metadata.

    The :mod:`mine_db` CLI scripts call :func:`mine_db.hooks.load_extra_models`
    before operating on SQLAlchemy metadata.  By pointing the
    ``MINE_DB_LOAD_MODELS`` environment variable at this function we ensure all
    ``mine_py`` models are imported and registered on ``Base.metadata``.

    New Feature:
        If config.model_locations is set, import models from specified packages
        instead of the default repom.models package.
    """
    if config.model_locations:
        from repom.utility import auto_import_models_from_list
        auto_import_models_from_list(
            package_names=config.model_locations,
            excluded_dirs=config.model_excluded_dirs,
            allowed_prefixes=config.allowed_package_prefixes,
            fail_on_error=config.model_import_strict
        )
    else:
        # デフォルト動作（後方互換性）
        # Importing the ``models`` package has the side-effect of registering every
        # SQLAlchemy model defined by the application.  The import is intentionally
        # local so the module is only loaded when the CLI needs it.
        from repom import models  # noqa: F401  # pylint: disable=unused-import


@dataclass
class MineDbConfig(Config):
    package_name: str = field(default="repom", init=False)

    # モデルが格納されてるディレクトリ
    set_models_hook: Optional[str] = field(default='repom.config:load_models', init=False, repr=False)

    # モデル自動インポート設定
    _model_locations: Optional[List[str]] = field(default=None, init=False, repr=False)
    _model_excluded_dirs: Optional[Set[str]] = field(default=None, init=False, repr=False)
    _allowed_package_prefixes: Set[str] = field(default_factory=lambda: {'repom.'}, init=False, repr=False)
    _model_import_strict: bool = field(default=False, init=False, repr=False)

    # DBの格納ディレクトリ (デフォルトで data_path に入る)
    _db_path: Optional[str] = field(default=None, init=False, repr=False)
    # DBファイル名 デフォルトで exec_env の値により'db.<exec_env>.sqlite' となる
    _db_file: Optional[str] = field(default=None, init=False, repr=False)
    # db接続用の文字列: 'sqlite:///%s/%s' % db_path, db_file の形式
    _db_url: Optional[str] = field(default=None, init=False, repr=False)
    # バックアップ先 - デフォルトで data_path/backups に入る
    _db_backup_path: Optional[str] = field(default=None, init=False, repr=False)

    def init(self):
        """初期化後の処理 - 必要なディレクトリを作成"""
        super().init()  # 親クラスのinitを呼び出し

        if self.auto_create_dirs:
            self._ensure_path_exists([
                self.db_backup_path
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
        """データベースURL - 'sqlite:///%s/%s' % db_path, db_file の形式"""
        if self._db_url is not None:
            return self._db_url
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
    def model_locations(self) -> Optional[List[str]]:
        """モデルをインポートするパッケージ名のリスト"""
        return self._model_locations

    @model_locations.setter
    def model_locations(self, value: Optional[List[str]]):
        self._model_locations = value

    @property
    def model_excluded_dirs(self) -> Optional[Set[str]]:
        """モデル検索時に除外するディレクトリ名のセット"""
        return self._model_excluded_dirs

    @model_excluded_dirs.setter
    def model_excluded_dirs(self, value: Optional[Set[str]]):
        self._model_excluded_dirs = value

    @property
    def allowed_package_prefixes(self) -> Set[str]:
        """インポートを許可するパッケージのプレフィックスのセット（セキュリティ対策）"""
        return self._allowed_package_prefixes

    @allowed_package_prefixes.setter
    def allowed_package_prefixes(self, value: Set[str]):
        self._allowed_package_prefixes = value

    @property
    def model_import_strict(self) -> bool:
        """モデルインポート失敗時に例外を送出するか（デフォルト: False = 警告のみ）"""
        return self._model_import_strict

    @model_import_strict.setter
    def model_import_strict(self, value: bool):
        self._model_import_strict = value


config = MineDbConfig()

config.root_path = str(Path(__file__).parent.parent)

# hook
config = get_config_from_hook(config)

config.init()


def load_set_model_hook_function():
    """モデル読み込み用のフック関数を実行する"""
    load_hook_function(config.set_models_hook)()
