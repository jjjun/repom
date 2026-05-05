# fast-domain ロギング移行ガイド

## 概要

repom の `make_timed_rotating_handler` を利用して、fast-domain のロギングを
日次ローテーション対応に更新します。

**変更対象ファイル**: 2ファイル

---

## 背景

repom のログファイル形式が以下のように変更されました。

| | 変更前 | 変更後 |
|---|---|---|
| ファイル名 | `main.log`（固定） | `main_2026-05-05.log`（日付付き） |
| ローテーション | なし | 毎日 0 時に自動切替 |
| 保持期間 | 無制限（肥大化） | 30 日分（古いファイルは自動削除） |

fast-domain も同じ形式に揃えます。

---

## 変更 1: `src/fast_domain/_/config_hook.py`

`log_file` プロパティのデフォルト値から `.log` 拡張子を除去します。  
`log_file` はベースパス（区分名のみ）を返すように変更します。

### 変更箇所（`log_file` プロパティ）

```python
# Before
@property
def log_file(self) -> Optional[str]:
    """ログファイル名。exec_env によりファイル名を切り替える"""
    return self._get_or_default(
        '_log_file',
        'test.log' if self.exec_env == 'test' else 'main.log',
    )

# After
@property
def log_file(self) -> Optional[str]:
    """ログファイルの区分名。exec_env によりファイル名を切り替える（拡張子・日付なし）"""
    return self._get_or_default(
        '_log_file',
        'test' if self.exec_env == 'test' else 'main',
    )
```

### 補足

`log_file_path` プロパティはそのままでOKです。

```python
@property
def log_file_path(self) -> Optional[str]:
    if not self.log_path:
        return None
    return str(Path(self.log_path) / self.log_file)
    # 例: data/fast_domain/logs/main  ← 拡張子・日付なしのベースパス
```

---

## 変更 2: `src/fast_domain/logging.py`

`FileHandler` を `repom.make_timed_rotating_handler` に差し替えます。

### 変更箇所（`get_logger` 関数内）

```python
# Before
import logging
from pathlib import Path

# After（import 追加）
import logging
from pathlib import Path
from repom.logging import make_timed_rotating_handler
```

```python
# Before（FileHandler を直接生成）
if isinstance(log_file_path, (str, Path)) and log_file_path:
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    package_root_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    package_root_logger.addHandler(file_handler)

# After（make_timed_rotating_handler に差し替え）
if isinstance(log_file_path, (str, Path)) and log_file_path:
    package_root_logger.setLevel(logging.DEBUG)

    file_handler = make_timed_rotating_handler(str(log_file_path))
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    package_root_logger.addHandler(file_handler)
```

`log_path.parent.mkdir(...)` の行は `make_timed_rotating_handler` 内部で処理されるため不要になります。

---

## 変更後の動作

| 設定 | 値 |
|---|---|
| アクティブなログファイル | `data/fast_domain/logs/main_2026-05-05.log` |
| テスト時 | `data/fast_domain/logs/test_2026-05-05.log` |
| ローテーション | 毎日 0 時 |
| 保持期間 | 30 日分 |

repom のログ（`data/repom/logs/main_2026-05-05.log`）とは独立したパスに出力されます。

---

## repom のバージョン要件

`make_timed_rotating_handler` は repom `v0.x.x`（コミット `4edd48a`）以降で利用可能です。

```python
# 利用可能な import 方法
from repom import make_timed_rotating_handler
from repom.logging import make_timed_rotating_handler  # どちらでも可
```
