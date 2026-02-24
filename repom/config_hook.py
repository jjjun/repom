from dataclasses import dataclass
from logging import config
from pathlib import Path
import os


def hook_config(config: dataclass) -> dataclass:
    """設定フック関数

    データベースタイプは EXEC_ENV に応じて自動設定:
    - test: SQLite（高速化のため :memory: DB を使用）
    - dev/prod: PostgreSQL

    使用例:
        # テスト実行（自動的に SQLite）
        poetry run pytest

        # 開発環境で PostgreSQL を使用
        $env:EXEC_ENV='dev'; poetry run repom_info
    """
    root_path = Path(__file__).parent.parent

    config.root_path = str(root_path)

    if config.package_name == 'repom':
        # モデルの自動登録設定
        config.model_locations = ['repom.examples.models']
        config.allowed_package_prefixes = {'repom.'}

        # データベースタイプの設定
        # テスト環境では SQLite（高速）、それ以外は PostgreSQL
        if os.getenv('EXEC_ENV') == 'test':
            config.db_type = 'sqlite'
        else:
            config.db_type = 'postgres'
            # config.db_type = 'sqlite'

        # PostgreSQL
        config.postgres.container.container_name = "repom_postgres"
        config.postgres.container.host_port = 5433
        config.postgres.port = 5433
        config.postgres.database = "repom"
        # pgAdmin
        config.pgadmin.container.enabled = True
        config.pgadmin.container.container_name = "repom_pgadmin"
        config.pgadmin.container.host_port = 5051
        # Redis
        config.redis.container.container_name = "repom_redis"
        config.redis.port = 6380

    return config
