import copy
import os
import shutil
import importlib
from pathlib import Path
import time
from typing import Optional, Union

from dataclasses import dataclass, field
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()


def load_hook_function(hook_path: str) -> Optional[callable]:
    """フック関数を動的にロードする"""
    try:
        # "module.path:function_name" 形式をパース
        if ':' in hook_path:
            module_path, function_name = hook_path.rsplit(':', 1)
        else:
            module_path = hook_path
            function_name = 'hook_config'

        # モジュールをインポート
        module = importlib.import_module(module_path)

        # 関数を取得
        if hasattr(module, function_name):
            return getattr(module, function_name)
        else:
            print(f"Warning: Function '{function_name}' not found in module '{module_path}'")
            return None

    except ImportError as e:
        print(f"Warning: Failed to import hook module '{module_path}': {e}")
        return None
    except Exception as e:
        print(f"Warning: Error loading hook function: {e}")
        return None


def get_config_from_hook(config: dataclass) -> dataclass:
    """環境変数で指定されたフック関数から設定を取得"""
    # 環境変数からフック関数のパスを取得
    hook_path = os.getenv('CONFIG_HOOK')

    if not hook_path or hook_path.strip() == '':
        return config  # フックが指定されていない場合は元の設定を返す

    # フック関数をロード
    hook_function = load_hook_function(hook_path)
    config = hook_function(config)
    return config


@dataclass
class Config:
    # init = False: __init__に含めない
    # repr = False: __repr__に表示されない(reprはオブジェクトの文字列表現)

    package_name: Optional[str] = field(default=None, init=False)
    root_path: Optional[str] = field(default=None)
    # 実行環境(dev/test/prod)
    exec_env: str = field(default=os.getenv('EXEC_ENV', 'dev'))
    # ディレクトリ自動作成フラグ(data)
    auto_create_dirs: bool = field(default=True)
    # データ保存先
    _data_path: Optional[str] = field(default=None, init=False, repr=False)
    # ログ関連
    _log_path: Optional[str] = field(default=None, init=False, repr=False)
    _log_file: Optional[str] = field(default=None, init=False, repr=False)
    # Docker Compose プロジェクト名
    _project_name: Optional[str] = field(default=None, init=False, repr=False)

    def _get_or_default(self, private_attr: str, default_value):
        """プライベート属性が設定されていれば返し、そうでなければデフォルト値を返す"""
        value = getattr(self, private_attr, None)
        if value is not None:
            return value
        return default_value

    def _ensure_path_exists(self, paths: Union[str, list[str]]):
        """指定されたパスまたはパスのリストが存在しない場合は作成"""
        if paths is None:
            return

        if isinstance(paths, str):
            paths = [paths]

        for p in paths:
            # None や空文字列をスキップ
            if not p:
                continue
            try:
                Path(p).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create directory {p}: {e}")

    def _retry_delete(self, path, retries=5, delay=1):
        for i in range(retries):
            try:
                shutil.rmtree(path)
                break
            except PermissionError as e:
                print(f"Retrying delete for {path}: {e}")
                time.sleep(delay)
        else:
            raise Exception(f"Failed to delete {path} after {retries} retries")

    def _delete_path_if_exists(self, path):
        if os.path.exists(path):
            self._retry_delete(path)

    def init(self):
        """初期化後の処理 - ディレクトリの自動作成"""
        if self.auto_create_dirs:
            self._ensure_path_exists([
                self.data_path,
                self.log_path,
            ])

    def cleanup(self) -> None:
        """クリーンアップ処理 - 必要に応じてオーバーライド"""
        pass

    def clone(self) -> "Config":
        """設定のクローンを作成"""
        return copy.deepcopy(self)

    @property
    def data_path(self) -> Optional[str]:
        """data_pathのgetter"""
        # 明示的に設定されている場合はそれを返す
        if self._data_path is not None:
            return self._data_path

        # root_pathから自動計算
        if self.root_path:
            path = Path(self.root_path) / 'data'
            if self.package_name:
                path = path / self.package_name
            return str(path)

        return None

    @data_path.setter
    def data_path(self, value: Optional[str]):
        """data_pathのsetter - 明示的に設定したい場合"""
        self._data_path = value

    @property
    def log_path(self) -> Optional[str]:
        """ログファイルの保存先。デフォルトで data_path となる"""
        return self._get_or_default(
            '_log_path',
            str(Path(self.data_path) / 'logs') if self.data_path else None,
        )

    @log_path.setter
    def log_path(self, value: Optional[str]):
        self._log_path = value

    @property
    def log_file(self) -> Optional[str]:
        """ログファイル名。exec_env によりファイル名を切り替える"""
        return self._get_or_default(
            '_log_file',
            'test.log' if self.exec_env == 'test' else 'main.log',
        )

    @log_file.setter
    def log_file(self, value: Optional[str]):
        self._log_file = value

    @property
    def log_file_path(self) -> Optional[str]:
        if not self.log_path:
            return None
        return str(Path(self.log_path) / self.log_file)

    @property
    def project_name(self) -> str:
        """Docker Compose プロジェクト名

        デフォルトで package_name を使用します。
        package_name が None の場合は "default" を返します。

        使用例:
            # hook_config でカスタマイズ
            def hook_config(config):
                config.project_name = "my_project"
                return config

        Returns:
            プロジェクト名（デフォルト: package_name または "default"）
        """
        if self._project_name is not None:
            return self._project_name
        return self.package_name or "default"

    @project_name.setter
    def project_name(self, value: Optional[str]):
        """Docker Compose プロジェクト名を設定"""
        self._project_name = value
