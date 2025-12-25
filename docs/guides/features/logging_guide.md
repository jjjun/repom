# repom ロギングガイド

repom は Python 標準の logging モジュールを使ったロギング機能を提供します。**ハイブリッドアプローチ**により、CLI ツール実行時とアプリケーション使用時の両方で柔軟に対応できます。

## 目次

- [基本的な使い方](#基本的な使い方)
- [CLI ツール実行時](#cli-ツール実行時)
- [アプリケーション使用時](#アプリケーション使用時)
- [config_hook でカスタマイズ](#config_hook-でカスタマイズ)
- [テスト時のログ制御](#テスト時のログ制御)
- [ログレベル変更](#ログレベル変更)
- [複数ログファイルへの分割](#複数ログファイルへの分割)
- [トラブルシューティング](#トラブルシューティング)

---

## 基本的な使い方

repom のロギングは以下の優先順位で動作します:

1. **アプリ側の設定（最優先）**: `logging.basicConfig()` または `dictConfig()`
2. **repom のデフォルト設定**: `config.log_file_path` を使用

### ロガーの取得

```python
from repom.logging import get_logger

logger = get_logger(__name__)
logger.debug("デバッグメッセージ")
logger.info("情報メッセージ")
logger.warning("警告メッセージ")
logger.error("エラーメッセージ")
logger.critical("致命的エラー")
```

**注意**: `__name__` を渡すと、`repom.{__name__}` という名前のロガーが返されます。

---

## CLI ツール実行時

repom の CLI ツール（`db_create`, `db_backup` など）を実行すると、repom のデフォルト設定が自動的に適用されます。

### デフォルトの動作

```bash
# 開発環境でデータベースを作成
$env:EXEC_ENV='dev'
poetry run db_create
```

**ログ出力先**:
- **ファイル**: `data/repom/logs/main.log`（デフォルト）
- **コンソール**: INFO 以上のメッセージ

**ログフォーマット**:
- **ファイル**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **コンソール**: `%(levelname)s: %(message)s`

### ログ内容の例

```bash
# data/repom/logs/main.log
2024-01-15 10:30:45,123 - repom.db - INFO - Database created: data/repom/db.dev.sqlite3

# コンソール出力
INFO: Database created: data/repom/db.dev.sqlite3
```

---

## アプリケーション使用時

アプリケーションから repom を使う場合、**アプリ側で `logging.basicConfig()` を呼ぶことを推奨**します。

### アプリ側で制御する（推奨）

```python
import logging
from repom.logging import get_logger

# アプリ側でログ設定（これが優先される）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# repom のロガーを取得
logger = get_logger(__name__)
logger.info("アプリケーション起動")
```

**動作**:
- repom のデフォルト設定はスキップされます
- アプリ側の設定（`app.log` + コンソール）のみが使われます

### アプリ側で設定しない場合

```python
from repom.logging import get_logger

# アプリ側で設定なし → repom のデフォルト設定が使われる
logger = get_logger(__name__)
logger.info("アプリケーション起動")
```

**動作**:
- repom のデフォルト設定が適用されます
- `data/repom/logs/main.log` + コンソール（INFO 以上）にログ出力

---

## config_hook でカスタマイズ

`config_hook` を使って、ログファイルのパスを変更できます。

### 外部プロジェクトでのカスタマイズ例（mine-py）

```python
# mine-py/src/mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # カスタムログパス
        self._log_path = 'logs/mine_py.log'
    
    @property
    def log_file_path(self):
        """カスタムログファイルパス"""
        return self._log_path

def get_repom_config():
    return MinePyConfig()
```

```bash
# .env ファイル
CONFIG_HOOK=mine_py.config:get_repom_config
```

**動作**:
- repom の CLI ツールを実行すると、`logs/mine_py.log` に出力される
- アプリ側で `logging.basicConfig()` を呼べば、そちらが優先される

---

## テスト時のログ制御

テスト時は、`EXEC_ENV=test` を設定することで、別のログファイルに出力できます。

### テスト時の設定

```python
# tests/conftest.py
import os
os.environ['EXEC_ENV'] = 'test'

import logging
from repom.config import config

# テスト時はログファイルを test.log に変更
config._log_path = 'logs/test.log'
```

### caplog を使ったテスト

```python
def test_logging(caplog):
    """ログが記録されることを確認"""
    from repom.logging import get_logger
    
    logger = get_logger('test')
    
    with caplog.at_level(logging.INFO):
        logger.info("テストメッセージ")
    
    assert "テストメッセージ" in caplog.text
```

---

## ログレベル変更

### repom のログレベルを変更

```python
import logging

# repom のルートロガーを取得
repom_logger = logging.getLogger('repom')

# WARNING 以上のみ出力
repom_logger.setLevel(logging.WARNING)
```

### 特定のモジュールのログレベルを変更

```python
import logging

# repom.base_repository のログレベルを DEBUG に変更
repo_logger = logging.getLogger('repom.base_repository')
repo_logger.setLevel(logging.DEBUG)
```

---

## 複数ログファイルへの分割

`dictConfig` を使って、モジュールごとに異なるログファイルに出力できます。

### dictConfig の例

```python
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'app': {
            'class': 'logging.FileHandler',
            'filename': 'logs/app.log',
            'formatter': 'default',
            'level': 'INFO'
        },
        'db': {
            'class': 'logging.FileHandler',
            'filename': 'logs/db.log',
            'formatter': 'default',
            'level': 'DEBUG'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO'
        }
    },
    'loggers': {
        'mine_py': {
            'handlers': ['app', 'console'],
            'level': 'INFO',
            'propagate': False
        },
        'repom': {
            'handlers': ['db', 'console'],
            'level': 'DEBUG',
            'propagate': False
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO'
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

**動作**:
- `mine_py.*` のログは `logs/app.log` に出力
- `repom.*` のログは `logs/db.log` に出力
- 全てのログは コンソール にも出力

---

## トラブルシューティング

### ログが出力されない

**原因1**: `logging.basicConfig()` を呼んでいない（アプリケーション使用時）

```python
# ❌ ログが出力されない
from repom.logging import get_logger
logger = get_logger(__name__)
logger.info("メッセージ")  # 出力されない

# ✅ logging.basicConfig() を呼ぶ
import logging
logging.basicConfig(level=logging.INFO)

from repom.logging import get_logger
logger = get_logger(__name__)
logger.info("メッセージ")  # 出力される
```

**原因2**: ログレベルが高すぎる

```python
# ❌ DEBUG が出力されない
logging.basicConfig(level=logging.INFO)
logger.debug("デバッグメッセージ")  # INFO 未満なので出力されない

# ✅ ログレベルを DEBUG に変更
logging.basicConfig(level=logging.DEBUG)
logger.debug("デバッグメッセージ")  # 出力される
```

### ログが二重に出力される

**原因**: `logging.basicConfig()` を複数回呼んでいる

```python
# ❌ 二重に出力される
logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)  # 2回目は無視されない場合がある

# ✅ ハンドラーをクリアしてから再設定
import logging
logging.shutdown()  # 既存のハンドラーをクリア
logging.basicConfig(level=logging.DEBUG)
```

### CLI ツールのログが出力されない

**原因**: `config.log_file_path` が `None`

```python
# repom/config.py を確認
from repom.config import config
print(config.log_file_path)  # None なら設定されていない
```

**解決策**: `config_hook` でカスタマイズ

```python
# mine-py/src/mine_py/config.py
class MinePyConfig(RepomConfig):
    @property
    def log_file_path(self):
        return 'logs/mine_py.log'  # カスタムパスを指定
```

---

## まとめ

- **CLI ツール実行時**: repom のデフォルト設定が自動適用（`config.log_file_path`）
- **アプリケーション使用時**: `logging.basicConfig()` を呼べば、そちらが優先
- **config_hook**: ログパスをプロジェクトごとにカスタマイズ可能
- **テスト時**: `EXEC_ENV=test` で別のログファイルに分離
- **ログレベル変更**: `logging.getLogger('repom').setLevel(logging.WARNING)`
- **複数ログファイル**: `dictConfig` でモジュールごとに分割

**推奨パターン**:
- アプリケーションでは、必ず `logging.basicConfig()` を呼ぶ
- CLI ツールでは、`config_hook` でログパスをカスタマイズ
- テストでは、`caplog` を使ってログを検証
