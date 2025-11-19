import os
import pytest
import logging
from repom.testing import create_test_fixtures


def pytest_configure(config):
    os.environ['EXEC_ENV'] = 'test'
    # CONFIG_HOOK を空文字列にすると py-mine の設定フックが無効化される
    # つまりは、このパッケージ単体で動かしたい場合には、CONFIG_HOOK を空にする
    os.environ['CONFIG_HOOK'] = ''

    # -vv オプション時のみデバッグログを有効化
    if config.option.verbose >= 2:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('data/repom/logs/test.log', encoding='utf-8')
            ]
        )
        logging.getLogger('repom').setLevel(logging.DEBUG)
    else:
        # 通常のテスト実行時は WARNING レベル以上のみ
        logging.getLogger('repom').setLevel(logging.WARNING)


# repom/testing.py のヘルパー関数を使用してフィクスチャを作成
db_engine, db_test = create_test_fixtures()
