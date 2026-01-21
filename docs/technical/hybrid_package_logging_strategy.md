# ハイブリッド型パッケージのロギング戦略

**対象読者**: CLI ツールを持つパッケージを開発する AI エージェント

**目的**: repom で実装したハイブリッドアプローチのロギング戦略を他のプロジェクト（例: fast-domain）に適用するためのガイド

---

## 問題の本質

### ハイブリッド型パッケージとは？

以下の2つの側面を持つパッケージを指します：

1. **CLI ツール**: パッケージ自身が実行可能なコマンドを提供
2. **ライブラリ**: 他のアプリケーションから import されて使用される

**例**:
- **repom**: `poetry run db_create` + `from repom import BaseRepository`
- **fast-domain**: `poetry run domain_command` + `from fast_domain.service import DomainService`
- **Alembic**: `alembic upgrade head` + `from alembic import context`
- **Django**: `django-admin migrate` + `from django.db import models`

### なぜロギングが問題になるのか？

Python のロギングベストプラクティスは**ライブラリの場合**と**アプリケーションの場合**で異なります：

#### ライブラリの推奨パターン（NullHandler のみ）

```python
# ライブラリの推奨パターン
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 何も出力しない
```

**理由**:
- ライブラリはログ設定を強制すべきではない
- アプリケーション側が `logging.basicConfig()` で全体を制御すべき

#### アプリケーションの推奨パターン（basicConfig）

```python
# アプリケーションの推奨パターン
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
```

**理由**:
- アプリケーションがログを完全に制御すべき
- ログ先、フォーマット、レベルを決定するのはアプリケーションの責任

### ハイブリッド型パッケージのジレンマ

ハイブリッド型パッケージは**両方の世界**に存在するため、どちらのパターンにも従えません：

| 側面 | 問題 |
|-----|------|
| **CLI ツール実行時** | `main.py` が実行されないため、`logging.basicConfig()` が呼ばれない → ログが出力されない |
| **ライブラリ使用時** | NullHandler だけでは不十分（CLI ツールのログが出力されない）、一方でログ設定を強制すると親アプリの設定と衝突する |

**具体例（repom の場合）**:

```bash
# CLI ツール実行時
poetry run db_create
# → アプリの main.py は実行されない
# → logging.basicConfig() は呼ばれない
# → ログが出力されない ❌

# ライブラリ使用時
# mine-py/main.py
logging.basicConfig(...)  # アプリ側の設定
from repom.base_repository import BaseRepository
repo = UserRepository()
# → repom が独自にログ設定すると衝突する ❌
```

---

## 解決策: ハイブリッドアプローチ

### 設計原則

**優先順位**:
1. アプリケーション側の `logging.basicConfig()` または `dictConfig()` （最優先）
2. パッケージのデフォルト設定（CLI ツール用）

**判定ロジック**:
```python
if not package_root_logger.handlers:
    # ハンドラーがない = アプリ側で設定していない
    # → パッケージのデフォルト設定を適用
else:
    # ハンドラーがある = アプリ側で設定済み
    # → 何もしない（アプリ側の設定を尊重）
```

### 実装パターン（repom の実例）

#### repom/logging.py

```python
"""
ロギングユーティリティ（ハイブリッドアプローチ）

優先順位:
1. アプリ側の logging.basicConfig() または dictConfig()（最優先）
2. repom のデフォルト設定（config.log_file_path を使用）
"""

import logging
from pathlib import Path

_logger_initialized = False


def get_logger(name: str) -> logging.Logger:
    """
    repom 用のロガーを取得（ハイブリッドアプローチ）
    
    デフォルト動作:
        - config.log_file_path に基づいてログを設定
        - repom のルートロガーにハンドラーがない場合のみ設定
    
    アプリ側で制御:
        - logging.basicConfig() を呼べば、そちらが優先される
        - repom のデフォルト設定はスキップされる
    
    Args:
        name: ロガー名（通常は __name__）
    
    Returns:
        logging.Logger: 設定済みロガー
    
    Examples:
        # CLI ツール（repom 単体）
        poetry run db_create
        → config.log_file_path + コンソールに出力
        
        # アプリ側で制御（優先される）
        import logging
        logging.basicConfig(handlers=[...])
        → アプリ側の設定に従う
        
        # アプリ側で設定なし（デフォルト動作）
        from repom.logging import get_logger
        logger = get_logger(__name__)
        → config.log_file_path + コンソールに出力
    """
    global _logger_initialized
    
    logger = logging.getLogger(f'repom.{name}')
    
    # 最初の呼び出し時のみ設定
    if not _logger_initialized:
        _logger_initialized = True
        
        # repom のルートロガーを取得
        repom_root_logger = logging.getLogger('repom')
        
        # ルートロガーにハンドラーがない場合のみ、デフォルト設定を追加
        if not repom_root_logger.handlers:
            from repom.config import config
            
            if config.log_file_path:
                # ログディレクトリを作成
                log_path = Path(config.log_file_path)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # ログレベルを設定
                repom_root_logger.setLevel(logging.DEBUG)
                
                # FileHandler を追加
                file_handler = logging.FileHandler(config.log_file_path, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                )
                repom_root_logger.addHandler(file_handler)
                
                # コンソール出力を追加（CLI ツール用）
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(
                    logging.Formatter('%(levelname)s: %(message)s')
                )
                repom_root_logger.addHandler(console_handler)
    
    return logger


__all__ = ['get_logger']
```

#### 使い方（各モジュールから呼び出し）

```python
# repom/base_repository.py
from repom.logging import get_logger

logger = get_logger(__name__)

class BaseRepository:
    def get_by_id(self, id):
        logger.debug(f"Fetching record with id={id}")
        # ...
```

### 動作パターン

| シナリオ | ルートロガーの状態 | ログ出力先 |
|---------|------------------|-----------|
| **CLI ツール実行** | ハンドラーなし | `config.log_file_path` + コンソール（パッケージの自動設定） |
| **アプリ側で `logging.basicConfig()`** | ハンドラーあり | アプリ側の設定（優先） |
| **アプリ側で設定なし** | ハンドラーなし | `config.log_file_path` + コンソール（パッケージの自動設定） |

---

## config_hook との統合

ハイブリッド型パッケージは通常、`config_hook` を使ってプロジェクトごとに設定をカスタマイズできます。

### repom の Config クラス

```python
# repom/config.py
class MineDbConfig:
    @property
    def log_file_path(self) -> str:
        """ログファイルパス"""
        log_path = self.log_path / 'main.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return str(log_path)
```

### 外部プロジェクトでのカスタマイズ（mine-py の例）

```python
# mine-py/src/mine_py/config.py
from repom.config import MineDbConfig

class MinePyConfig(MineDbConfig):
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

## fast-domain への適用手順

### Step 1: logging.py を作成

```python
# fast_domain/logging.py
"""
ロギングユーティリティ（ハイブリッドアプローチ）

優先順位:
1. アプリ側の logging.basicConfig() または dictConfig()（最優先）
2. fast-domain のデフォルト設定（config.log_file_path を使用）
"""

import logging
from pathlib import Path

_logger_initialized = False


def get_logger(name: str) -> logging.Logger:
    """
    fast-domain 用のロガーを取得（ハイブリッドアプローチ）
    
    Args:
        name: ロガー名（通常は __name__）
    
    Returns:
        logging.Logger: 設定済みロガー
    """
    global _logger_initialized
    
    logger = logging.getLogger(f'fast_domain.{name}')
    
    # 最初の呼び出し時のみ設定
    if not _logger_initialized:
        _logger_initialized = True
        
        # fast-domain のルートロガーを取得
        root_logger = logging.getLogger('fast_domain')
        
        # ルートロガーにハンドラーがない場合のみ、デフォルト設定を追加
        if not root_logger.handlers:
            from fast_domain.config import config  # あなたの config クラス
            
            if hasattr(config, 'log_file_path') and config.log_file_path:
                # ログディレクトリを作成
                log_path = Path(config.log_file_path)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # ログレベルを設定
                root_logger.setLevel(logging.DEBUG)
                
                # FileHandler を追加
                file_handler = logging.FileHandler(config.log_file_path, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                )
                root_logger.addHandler(file_handler)
                
                # コンソール出力を追加（CLI ツール用）
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(
                    logging.Formatter('%(levelname)s: %(message)s')
                )
                root_logger.addHandler(console_handler)
    
    return logger


__all__ = ['get_logger']
```

### Step 2: Config クラスに log_file_path を追加

```python
# fast_domain/config.py
class FastDomainConfig:
    @property
    def log_file_path(self) -> str:
        """ログファイルパス"""
        # あなたのログディレクトリ構造に合わせて変更
        log_path = Path('data/fast_domain/logs/main.log')
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return str(log_path)
```

### Step 3: 各モジュールからロガーを取得

```python
# fast_domain/service.py
from fast_domain.logging import get_logger

logger = get_logger(__name__)

class DomainService:
    def process(self):
        logger.info("Processing started")
        # ...
        logger.debug("Processing details")
        # ...
        logger.info("Processing completed")
```

### Step 4: テストを作成

```python
# tests/unit_tests/test_logging.py
import logging
import pytest
from pathlib import Path
from unittest.mock import patch

from fast_domain.logging import get_logger


class TestGetLogger:
    """get_logger() の動作確認（ハイブリッドアプローチ）"""
    
    def test_get_logger_returns_logger(self):
        """ロガーが正しく取得できる"""
        logger = get_logger('test')
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'fast_domain.test'
    
    def test_get_logger_with_basicConfig(self, tmp_path, monkeypatch):
        """
        アプリ側で logging.basicConfig() を呼んだ場合、
        fast-domain のデフォルト設定はスキップされる
        """
        # basicConfig() を先に呼ぶ（ハンドラーを追加）
        app_log_file = tmp_path / "app.log"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(name)s - %(message)s',
            handlers=[logging.FileHandler(app_log_file)]
        )
        
        # fast-domain のルートロガーにハンドラーが追加されているか確認
        root_logger = logging.getLogger('fast_domain')
        assert len(root_logger.handlers) > 0  # basicConfig() でハンドラーが追加される
        
        # get_logger() を呼んでも、追加のハンドラーは追加されない
        logger = get_logger('test')
        assert logger.name == 'fast_domain.test'
        
        # ハンドラー数が変わらないことを確認
        initial_count = len(root_logger.handlers)
        _ = get_logger('test2')
        assert len(root_logger.handlers) == initial_count
    
    def test_default_logging_setup(self, tmp_path, monkeypatch):
        """
        ハンドラーがない場合、fast-domain のデフォルト設定が適用される
        """
        # fast_domain/logging.py の _logger_initialized をリセット
        import fast_domain.logging
        fast_domain.logging._logger_initialized = False
        
        # logging の状態をリセット
        logging.shutdown()
        
        # fast-domain のルートロガーをリセット
        root_logger = logging.getLogger('fast_domain')
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # config.log_file_path をモック（monkeypatch を使用）
        log_file = tmp_path / "test.log"
        from fast_domain.config import config
        monkeypatch.setattr(config.__class__, 'log_file_path', property(lambda self: log_file))
        
        logger = get_logger('test')
        
        # fast-domain のルートロガーにハンドラーが追加されているか確認
        assert len(root_logger.handlers) == 2  # FileHandler + ConsoleHandler
        
        # ログファイルが作成されているか確認
        logger.debug("Test message")
        assert log_file.exists()
        
        # ログファイルの内容を確認
        content = log_file.read_text(encoding='utf-8')
        assert "Test message" in content
        assert "fast_domain.test" in content
```

---

## テスト実行

```bash
# fast-domain のテスト
poetry run pytest tests/unit_tests/test_logging.py -v

# 全テスト
poetry run pytest
```

---

## まとめ

### ハイブリッドアプローチの利点

1. ✅ **CLI ツールのログが出力される**
   - `poetry run domain_command` でログが見える
   - デバッグが容易になる

2. ✅ **アプリ側が完全に制御できる**
   - `logging.basicConfig()` が優先される
   - パッケージは邪魔をしない

3. ✅ **デフォルトで動作する**
   - アプリ側で何もしなくても、パッケージのログが出力される
   - ゼロ設定で使える

4. ✅ **config_hook で柔軟にカスタマイズ**
   - CLI ツールのログ先を変更可能
   - プロジェクトごとに異なる設定が可能

### 実装チェックリスト

- [ ] `package/logging.py` を作成（`get_logger()` 関数）
- [ ] Config クラスに `log_file_path` プロパティを追加
- [ ] 各モジュールで `get_logger(__name__)` を使用
- [ ] テストを作成（6つのテストケース）
- [ ] ドキュメントを作成（`docs/guides/logging_guide.md`）
- [ ] README.md にロギングガイドへのリンクを追加

### 参考資料

- **repom の実装**: [repom/logging.py](../../repom/logging.py)
- **repom のテスト**: [tests/unit_tests/test_logging.py](../../tests/unit_tests/test_logging.py)
- **repom のガイド**: [docs/guides/logging_guide.md](../guides/logging_guide.md)

---

## 他のプロジェクトへの適用

このドキュメントは、以下のようなハイブリッド型パッケージに適用できます：

- **fast-domain**: ドメイン駆動設計のツールキット
- **mine-py**: データマイニングパッケージ
- **その他**: CLI ツールを持つあらゆる Python パッケージ

**重要**: パッケージ名（`repom` → `fast_domain`）、config クラスのパス、ログディレクトリ構造を適切に変更してください。

---

最終更新: 2025-11-19
