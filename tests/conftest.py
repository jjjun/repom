import os


def pytest_configure(config):
    os.environ['EXEC_ENV'] = 'test'
    # CONFIG_HOOK を空文字列にすると py-mine の設定フックが無効化される
    # つまりは、このパッケージ単体で動かしたい場合には、CONFIG_HOOK を空にする
    os.environ['CONFIG_HOOK'] = ''
