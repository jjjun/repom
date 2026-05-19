# CONFIG_HOOK ガイド

## 概要

`CONFIG_HOOK` は、repom の起動時に設定オブジェクトを外部プロジェクト側で差し替えるための仕組みです。
hook の読み込み処理は `basekit.config_hook` が提供し、repom はその基盤を使って `RepomConfig` を適用します。

通常の利用では、外部プロジェクトで `RepomConfig` を継承した設定クラスを作り、`CONFIG_HOOK` に `module:function` 形式で hook 関数を指定します。

---

## 基本的な使い方

### 1. hook 関数を定義する

```python
# myapp/config.py
from repom.config import RepomConfig


class MyAppConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        self.db_name = "myapp"
        self.model_locations = ["myapp.models"]
        self.allowed_package_prefixes = {"myapp.", "repom."}


def get_repom_config():
    return MyAppConfig()
```

既存の `config` を受け取って変更する形も使えます。

```python
# myapp/config.py
from repom.config import RepomConfig


def hook_config(config: RepomConfig) -> RepomConfig:
    config.db_type = "postgres"
    config.db_name = "myapp"
    config.model_locations = ["myapp.models"]
    config.allowed_package_prefixes = {"myapp.", "repom."}
    return config
```

### 2. 環境変数で指定する

```bash
# .env
CONFIG_HOOK=myapp.config:get_repom_config
```

PowerShell では次のように指定します。

```powershell
$env:CONFIG_HOOK='myapp.config:get_repom_config'
```

---

## repom と basekit の責務

- `basekit.config_hook`: `CONFIG_HOOK` の読み取り、hook 関数の import、エラー処理を提供します。
- `repom.config.RepomConfig`: DB、モデル自動インポート、ログ、パスなど repom 固有の設定を提供します。
- `repom._.config_hook`: 以前の互換 import でしたが、現在は削除されています。

`ConfigHookLoadError` を直接扱う必要がある場合は、`basekit.config_hook` から import してください。

```python
from basekit.config_hook import ConfigHookLoadError
```

---

## よく使う設定例

### モデル自動インポート

```python
from repom.config import RepomConfig


class MyAppConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        self.model_locations = ["myapp.models", "myapp.modules.user"]
        self.model_excluded_dirs = {"tests", "migrations", "__pycache__"}
        self.allowed_package_prefixes = {"myapp.", "repom."}
        self.model_import_strict = True


def get_repom_config():
    return MyAppConfig()
```

### PostgreSQL を使う

```python
from repom.config import RepomConfig


def get_repom_config():
    config = RepomConfig()
    config.db_type = "postgres"
    config.db_name = "myapp"
    config.postgres.user = "myapp"
    config.postgres.password = "myapp_dev"
    config.postgres.container.container_name = "myapp_postgres"
    config.postgres.container.host_port = 5434
    return config
```

### Redis / PostgreSQL コンテナ名を分ける

```python
from repom.config import RepomConfig


def get_repom_config():
    config = RepomConfig()
    config.postgres.container.container_name = "myapp_postgres"
    config.redis.container.container_name = "myapp_redis"
    config.redis.port = 6381
    config.redis.container.host_port = 6381
    return config
```

---

## 動作フロー

1. `repom.config` がデフォルトの `RepomConfig` を作成する
2. `basekit.config_hook.get_config_from_hook()` が `CONFIG_HOOK` を読む
3. `CONFIG_HOOK` が未設定ならデフォルト設定をそのまま返す
4. `CONFIG_HOOK` が設定されていれば `module:function` を import する
5. hook 関数を実行し、返された config を repom の実行時設定として使う
6. 返却後に `config.init()` が呼ばれ、パス作成などの初期化が行われる

---

## エラーと確認方法

`CONFIG_HOOK` に指定した module が import できない、関数が存在しない、指定先が callable ではない場合、`basekit.config_hook.ConfigHookLoadError` が送出されます。
設定ミスを warning だけで無視しないため、CI/CD や外部プロジェクト連携では hook パスを明示的に検証してください。

```python
import os

print("CONFIG_HOOK:", os.getenv("CONFIG_HOOK"))
```

hook パスは Python の module path で指定します。ファイルパスではありません。

```bash
# 正しい
CONFIG_HOOK=myapp.config:get_repom_config

# 間違い
CONFIG_HOOK=myapp/config.py:get_repom_config
```

---

## ベストプラクティス

1. hook 関数は軽量に保つ
2. `RepomConfig` を継承したクラスを返すか、受け取った `config` を変更して返す
3. モデル自動インポートを使う場合は `allowed_package_prefixes` を明示する
4. 環境ごとの差分は `EXEC_ENV` を読んで最小限に分岐する
5. `repom._.config_hook` は使わず、共通 hook API は `basekit.config_hook` を直接使う

---

## 機能別 config モジュール

`RepomConfig` は引き続き `repom.config` から import します。PostgreSQL、Redis、SQLite の個別設定クラスは機能別モジュールにも配置されています。

```python
from repom.postgres.config import PostgresConfig, PostgresContainerConfig
from repom.redis.config import RedisConfig, RedisContainerConfig
from repom.sqlite.config import SqliteConfig
```

Config 系クラスは機能別モジュールから直接 import します。複数機能をまとめる設定では `RepomConfig` を使います。

---

## 関連ドキュメント

- [README.md の設定概要](../../../README.md#環境変数)
- [モデル自動インポートガイド](auto_import_models_guide.md)
- [ロギングガイド](logging_guide.md)
- [PostgreSQL セットアップガイド](../postgresql/postgresql_setup_guide.md)
