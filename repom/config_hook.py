from dataclasses import dataclass
from pathlib import Path


def hook_config(config: dataclass) -> dataclass:
    """設定フック関数
    """
    root_path = Path(__file__).parent.parent

    config.root_path = str(root_path)

    # モデルの自動登録設定
    config.model_locations = ['repom.examples.models']
    config.allowed_package_prefixes = {'repom.'}

    return config
