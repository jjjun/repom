# repom ロギングガイド

repom は Python 標準の `logging` を使います。汎用 handler と設定関数は
`basekit.logging` が所有し、repom は package 名と `RepomConfig` を接続します。

## 基本

repom 内部では次のように logger を取得します。

```python
from repom.logging import get_logger

logger = get_logger(__name__)
logger.info("operation completed")
```

`repom.database` は import 時に `get_logger(__name__)` を呼びます。そのため
`import repom` だけで、repom root logger に handler がなければ `config.log_file_path`
を使った既定の file / console handler が設定されます。アプリケーションが先に
`logging.basicConfig()` や `dictConfig()` で handler を設定している場合は、その設定を
優先します。

利用側アプリケーションは、repom を import する前に logging を設定してください。

ログレベルは `EXEC_ENV` から決まり、`prod` では `INFO`、それ以外では `DEBUG` です。
`production` も `prod` と同じ扱いになり、環境名の大文字小文字や前後の空白は区別されません。
`LOG_LEVEL` 環境変数を設定すると、大文字小文字を区別せずにこの既定値を上書きできます。
ファイル handler にはこのレベルが設定され、console handler には `max(ログレベル, INFO)` が
設定されます。そのため、本番環境で `DEBUG` のファイル出力を必要とする場合は、
`LOG_LEVEL=DEBUG` を設定してください。

`LOG_LEVEL` には有効な logging level 名を指定してください。無効な値を指定すると、最初に
logger を使用した時点で `ValueError` が発生します。

既定の log file は `<data_path>/logs/main_YYYY-MM-DD.log` に作成され、
`EXEC_ENV=test` では `test_...` の名前になります。file の mode は `0600` です。
利用側の config hook で `config.log_level` を設定して、log level を変更できます。

## 日次ファイル

`make_timed_rotating_handler()` と `DateNamedDailyFileHandler` は公開 API です。
active file は `<stem>_<YYYY-MM-DD>.log` 形式です。

```python
import logging

from repom.logging import make_timed_rotating_handler

handler = make_timed_rotating_handler(
    "data/logs/myapp",
    backup_count=30,
)
logger = logging.getLogger("myapp")
logger.addHandler(handler)
```

handler の汎用仕様は `basekit.logging` が正本です。repom 固有の動作は
[`tests/unit_tests/test_logging.py`](../../../tests/unit_tests/test_logging.py) で
確認できます。

## SQLAlchemy query log

```python
def hook_config(config):
    config.enable_sqlalchemy_echo = True
    config.sqlalchemy_echo_level = "INFO"  # または "DEBUG"
    return config
```

環境変数 helper を使う場合:

```dotenv
SQLALCHEMY_ECHO=true
SQLALCHEMY_ECHO_LEVEL=INFO
```

```python
from repom.config_hooks.database import apply_database_env_overrides


def hook_config(config):
    apply_database_env_overrides(config)
    return config
```

`INFO` と `DEBUG` はどちらも SQL 文に加えてバインドパラメータの実際の値をログへ
出力します（`DEBUG` はさらに実行結果の行データも出力します）。パスワードハッシュ
やトークンなど機微な値も記録され得るため、本番相当の実データを扱う環境で安易に
有効化しないでください。値を伏せて SQL 文の傾向だけを確認したい場合は
`config.sqlalchemy_hide_parameters`（デフォルト `True`。環境変数
`SQLALCHEMY_HIDE_PARAMETERS`）を有効のままにしておいてください。

## module ごとのレベル

```python
import logging

logging.getLogger("repom").setLevel(logging.WARNING)
logging.getLogger("repom.repositories.base_repository").setLevel(logging.DEBUG)
```

## テスト

通常の `uv run pytest` は repom logger を WARNING 以上に抑えます。
`uv run pytest -vv -s` を明示した場合だけ `tests/conftest.py` が DEBUG log と stdout
を有効にします。

## トラブルシューティング

- log が出ない: application handler または `config.log_file_path` を確認。
- handler が重複する: app と library の両方で同じ logger に handler を追加していないか確認。
- SQL log が出ない: hook 適用後の `enable_sqlalchemy_echo` を
  `uv run python -c "from repom.config import config; print(config.enable_sqlalchemy_echo)"` で確認。
- 日次 file の場所が違う: `config.log_file_path` と `EXEC_ENV` を確認。

関連資料:

- [CONFIG_HOOK](config_hook_guide.md)
- [ロギング設計の履歴](../../technical/hybrid_package_logging_strategy.md)
- [`repom/logging.py`](../../../repom/logging.py)
