# Issue #012: ロギング機能の追加

**ステータス**: 🟢 進行中

**作成日**: 2025-11-18

**優先度**: 中

---

## 問題の説明

現在、repom にはロギング機能がありません。そのため、以下の問題があります：

1. **デバッグが困難**
   - データベース操作の追跡ができない
   - トランザクションの開始・コミット・ロールバックが見えない
   - エラー発生時の原因特定に時間がかかる

2. **運用時の可視性不足**
   - どのクエリが実行されているか不明
   - パフォーマンス問題の発見が遅れる
   - エラーログが残らない

3. **各プロジェクトでの重複実装**
   - fast-domain、mine-py などが独自にログを追加
   - 一貫性のないログフォーマット

---

## 提案される解決策

repom に**ハイブリッドアプローチのロギングインフラ**を追加する。

### 設計方針：ハイブリッドアプローチ

repom は以下の2つの世界で使われることを考慮した設計を採用します：

#### 世界1: CLI ツール（repom 単体での実行）

```bash
# repom の CLI ツール
poetry run db_create
poetry run alembic upgrade head
```

**問題点**:
- アプリケーション側の `main.py` は実行されない
- `logging.basicConfig()` が適用されない
- ログが出力されない

**解決策**:
- repom が `config.log_file_path` を使ってデフォルト設定を提供
- CLI ツールのログが自動的に出力される

#### 世界2: アプリケーションコード（BaseRepository など）

```python
# mine-py/main.py
from repom.base_repository import BaseRepository
repo = UserRepository()
user = repo.get_by_id(1)
```

**要件**:
- アプリケーション側がログを完全に制御したい
- `logging.basicConfig()` で設定を行いたい

**解決策**:
- アプリ側で `logging.basicConfig()` を呼べば、そちらが優先される
- repom のデフォルト設定は適用されない

### ハイブリッドアプローチの実装

```python
# repom/logging.py
def get_logger(name: str) -> logging.Logger:
    """
    repom 用のロガーを取得（ハイブリッドアプローチ）
    
    デフォルト動作:
        - config.log_file_path に基づいて最低限のログ設定を提供
        - repom のルートロガーにハンドラーがない場合のみ設定
    
    アプリ側で制御:
        - logging.basicConfig() を呼べば、そちらが優先される
        - repom のデフォルト設定はスキップされる
    """
```

### 動作パターン

| シナリオ | repom のルートロガーの状態 | ログ出力先 |
|---------|-------------------------|-----------|
| **CLI ツール実行** | ハンドラーなし | `config.log_file_path` + コンソール（repom の自動設定） |
| **アプリ側で `logging.basicConfig()`** | ハンドラーあり | アプリ側の設定（優先） |
| **アプリ側で設定なし** | ハンドラーなし | `config.log_file_path` + コンソール（repom の自動設定） |

### 設計の特徴

1. ✅ **CLI ツールのログが出力される**
   - `poetry run db_create` でログが見える
   - デバッグが容易になる

2. ✅ **アプリ側が完全に制御できる**
   - `logging.basicConfig()` が優先される
   - repom は邪魔をしない

3. ✅ **デフォルトで動作する**
   - アプリ側で何もしなくても、repom のログが出力される
   - ゼロ設定で使える

4. ✅ **config_hook で柔軟にカスタマイズ**
   - CLI ツールのログ先を変更可能
   - プロジェクトごとに異なる設定が可能

---

## 実装範囲

### Phase 1: ロギングインフラ構築 ✅

**新規ファイル**:
- `repom/logging.py` - `get_logger()` 関数のみ

**変更ファイル**:
- なし

### Phase 2: BaseRepository にログ追加 🚧

**変更ファイル**:
- `repom/base_repository.py`

**ログポイント**:
- `get_by_id()` - データ取得
- `find()` - クエリ実行
- `save()` - データ保存
- `delete()` - データ削除

**ログレベル**:
- `DEBUG`: クエリ詳細、パラメータ
- `INFO`: 成功した操作（件数、ID）
- `WARNING`: データ未発見、削除操作
- `ERROR`: 例外、制約違反

### Phase 3: session.py にログ追加 📝

**変更ファイル**:
- `repom/session.py`

**ログポイント**:
- トランザクション開始
- コミット成功
- ロールバック（例外詳細）
- セッションクローズ

### Phase 4: ドキュメント作成 📝

**新規ファイル**:
- `docs/guides/logging_guide.md` - 使い方ガイド
- テスト: `tests/unit_tests/test_logging.py`

---

## 実装詳細

### repom/logging.py（ハイブリッドアプローチ版）

```python
"""
ロギングユーティリティ（ハイブリッドアプローチ）

repom は以下の優先順位でログ設定を行います:
1. アプリ側の logging.basicConfig() または dictConfig()（最優先）
2. repom のデフォルト設定（config.log_file_path を使用）

CLI ツール実行時:
    repom のデフォルト設定が適用されます。
    
アプリケーション実行時:
    アプリ側で logging.basicConfig() を呼べば、そちらが優先されます。
    呼ばなければ、repom のデフォルト設定が使われます。
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
        → repom/data/repom/logs/main.log + コンソール
        
        # アプリ側で制御（優先される）
        import logging
        logging.basicConfig(handlers=[...])
        → アプリ側の設定に従う
        
        # アプリ側で設定なし（デフォルト動作）
        from repom.logging import get_logger
        logger = get_logger(__name__)
        → config.log_file_path + コンソール
    
    Note:
        最初の呼び出し時に、repom のルートロガーにハンドラーがない場合のみ、
        config.log_file_path に基づいてデフォルト設定を追加します。
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

### BaseRepository のログ追加例

```python
# repom/base_repository.py
from repom.logging import get_logger

logger = get_logger(__name__)  # repom.base_repository

class BaseRepository(Generic[T]):
    def get_by_id(self, id: Any) -> Optional[T]:
        logger.debug(f"Fetching {self.model.__name__} by id={id}")
        result = self.session.get(self.model, id)
        
        if result:
            logger.debug(f"Found {self.model.__name__} id={id}")
        else:
            logger.warning(f"Not found {self.model.__name__} id={id}")
        
        return result
    
    def find(self, filter_params: Optional[FilterParams] = None) -> List[T]:
        logger.debug(
            f"Query {self.model.__name__} with filters: "
            f"{filter_params.dict() if filter_params else 'None'}"
        )
        
        query = self._build_query(filter_params)
        results = query.all()
        
        logger.info(f"Found {len(results)} {self.model.__name__} records")
        return results
    
    def save(self, entity: T) -> T:
        is_new = not self._is_persisted(entity)
        operation = 'Creating' if is_new else 'Updating'
        
        logger.info(f"{operation} {self.model.__name__}")
        self.session.add(entity)
        self.session.flush()
        
        logger.debug(f"Saved {self.model.__name__} id={self._get_id(entity)}")
        return entity
    
    def delete(self, entity: T) -> None:
        logger.warning(
            f"Deleting {self.model.__name__} id={self._get_id(entity)}"
        )
        self.session.delete(entity)
        self.session.flush()
```

### session.py のログ追加例

```python
# repom/session.py
from repom.logging import get_logger

logger = get_logger(__name__)  # repom.session

@contextmanager
def transaction() -> Generator[Session, None, None]:
    session = SessionLocal()
    logger.debug("Transaction started")
    
    try:
        with session.begin():
            yield session
        logger.info("Transaction committed")
    except Exception as e:
        logger.error(f"Transaction rolled back: {e}", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()
        logger.debug("Session closed")
```

---

## アプリケーション側での使用例

### ケース1: CLI ツール実行（repom 単体）

```bash
# mine-py ディレクトリから実行
poetry run db_create
```

**動作**:
- repom のルートロガーにハンドラーがない
- → `config.log_file_path` を使って自動設定
- → `mine-py/data/repom/logs/main.log` + コンソールに出力

**ログ出力先**:
- **ファイル**: `mine-py/data/repom/logs/main.log` (config_hook で決定)
- **コンソール**: 標準出力（INFO レベル以上）

---

### ケース2: アプリ側で logging.basicConfig() を使用

```python
# mine-py/main.py
import logging

# アプリ側でログ設定（これが優先される）
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mine-py/data/logs/app.log'),
        logging.StreamHandler()
    ]
)

# repom を使う
from repom.base_repository import BaseRepository
from mine_py.models.user import User

repo = BaseRepository(User)
user = repo.get_by_id(1)
```

**動作**:
- `logging.basicConfig()` が先に呼ばれている
- repom のルートロガーに**既にハンドラーがある**
- → repom の自動設定は**スキップされる**
- → アプリ側の設定が適用される

**ログ出力先**:
- **ファイル**: `mine-py/data/logs/app.log` ← アプリ側の設定
- **コンソール**: 標準出力

---

### ケース3: アプリ側でログ設定なし

```python
# mine-py/main.py
# logging.basicConfig() を呼ばない

from repom.base_repository import BaseRepository
from mine_py.models.user import User

repo = BaseRepository(User)
user = repo.get_by_id(1)
```

**動作**:
- アプリ側でログ設定をしていない
- repom のルートロガーにハンドラーがない
- → repom の自動設定が適用される

**ログ出力先**:
- **ファイル**: `mine-py/data/repom/logs/main.log` ← repom のデフォルト
- **コンソール**: 標準出力

---

### ケース4: dictConfig() で個別ログファイル設定

```python
# mine-py/main.py
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
        'repom_file': {
            'class': 'logging.FileHandler',
            'filename': 'data/logs/repom.log',
            'formatter': 'default'
        },
        'mine_py_file': {
            'class': 'logging.FileHandler',
            'filename': 'data/logs/mine-py.log',
            'formatter': 'default'
        }
    },
    'loggers': {
        'repom': {
            'handlers': ['repom_file'],
            'level': 'DEBUG'
        },
        'mine_py': {
            'handlers': ['mine_py_file'],
            'level': 'INFO'
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

**動作**:
- `dictConfig()` が repom のルートロガーを設定
- repom のルートロガーに**既にハンドラーがある**
- → repom の自動設定は**スキップされる**

**ログ出力先**:
- **repom のログ**: `data/logs/repom.log`
- **mine-py のログ**: `data/logs/mine-py.log`

---

### ケース5: fast-domain での使用（logging_config.py を使用）

```python
# fast_domain/main.py
from fast_domain.logging_config import setup_logging
from fast_domain.config import config

# アプリケーション起動時にログ設定
setup_logging(
    log_file_path=config.log_file_path,
    level=logging.DEBUG if config.debug else logging.INFO
)

# これで repom のログも fast_domain の設定に従う
```

**動作**:
- `setup_logging()` がルートロガーを設定
- repom のルートロガーに**既にハンドラーがある**
- → repom の自動設定は**スキップされる**

**ログ出力先**:
- **ファイル**: `config.log_file_path` で指定した場所
- **コンソール**: 標準出力

---

## テスト計画

### tests/unit_tests/test_logging.py

```python
def test_get_logger_returns_logger():
    """get_logger がロガーを返すこと"""
    logger = get_logger('test')
    assert isinstance(logger, logging.Logger)
    assert logger.name == 'repom.test'

def test_get_logger_has_null_handler():
    """デフォルトで NullHandler が設定されていること"""
    logger = get_logger('test')
    assert len(logger.handlers) > 0
    assert isinstance(logger.handlers[0], logging.NullHandler)

def test_logging_does_not_output_by_default():
    """デフォルトでは何も出力されないこと"""
    logger = get_logger('test')
    # ログを出力してもエラーにならない
    logger.debug("test message")
    logger.info("test message")
    logger.warning("test message")

def test_logging_respects_application_config():
    """アプリケーション側の設定が反映されること"""
    # アプリケーション側でログ設定
    logging.basicConfig(level=logging.DEBUG)
    
    logger = get_logger('test')
    # ログが出力される（テストでは検証しない）
    logger.debug("test message")
```

---

## 影響範囲

### 新規作成ファイル
- `repom/logging.py` - ロギングユーティリティ
- `docs/guides/logging_guide.md` - 使い方ガイド
- `tests/unit_tests/test_logging.py` - テスト

### 変更ファイル
- `repom/base_repository.py` - ログ追加
- `repom/session.py` - ログ追加
- `README.md` - ログガイドへのリンク追加

### 既存機能への影響
- ✅ **後方互換性あり**
  - CLI ツールのログが自動的に出力される（改善）
  - アプリ側で `logging.basicConfig()` を使えば、そちらが優先される
  - 既存のアプリケーションコードは変更不要
- ✅ **パフォーマンス影響最小**
  - ハンドラーの有無チェックは最初の1回のみ
  - ログ出力自体は Python 標準 `logging` の性能に依存
- ✅ **他のパッケージへの影響なし**
  - repom のルートロガー（`repom.*`）のみ設定
  - 他のロガーには一切影響しない

---

## ハイブリッドアプローチの利点と懸念点

### ✅ 利点

1. **CLI ツールのログが出力される**
   - `poetry run db_create` でログが見える
   - Alembic マイグレーションのログが追跡できる
   - デバッグが容易になる

2. **アプリ側が完全に制御できる**
   - `logging.basicConfig()` が優先される
   - repom は邪魔をしない
   - 従来の使い方が変わらない

3. **デフォルトで動作する**
   - アプリ側で何もしなくても、repom のログが出力される
   - ゼロ設定で使える

4. **config_hook で柔軟にカスタマイズ**
   - CLI ツールのログ先を変更可能
   - プロジェクトごとに異なる設定が可能

### ⚠️ 懸念点（要議論）

1. **ライブラリの原則からの逸脱**
   - Python ライブラリのベストプラクティスは「NullHandler のみ」
   - repom が自動的にログファイルを作成・出力する
   - **議論点**: repom は「ライブラリ」ではなく「共有基盤パッケージ」と考えるべきか？

2. **ルートロガーのハンドラー有無による分岐**
   - `if not repom_root_logger.handlers:` による判定
   - アプリ側の設定タイミングに依存する
   - **議論点**: この判定ロジックは十分に安全か？

3. **テスト時の動作**
   - テスト実行時にログファイルが作成される
   - `EXEC_ENV=test` で `test.log` に出力される
   - **議論点**: テスト時はログを完全に無効化すべきか？

4. **複数のロガー設定の競合**
   - アプリ側で複数回 `logging.basicConfig()` を呼ぶ場合
   - repom の自動設定との優先順位
   - **議論点**: より明示的な制御方法が必要か？

5. **config.log_file_path への依存**
   - `config.log_file_path` が None の場合の挙動
   - config_hook が設定されていない場合
   - **議論点**: フォールバック戦略は適切か？

---

## ベストプラクティス

### DO（推奨）

✅ **repom 側**:
- `get_logger(__name__)` でロガーを取得
- NullHandler のみ使用
- ログ設定をアプリ側に委譲

✅ **アプリケーション側**:
- `logging.basicConfig()` または `dictConfig()` でログ設定
- `logging.getLogger('repom')` でレベルを制御
- ログファイルパスを自由に設定

### DON'T（非推奨）

❌ **repom 側でやってはいけないこと**:
- `logging.basicConfig()` を呼ばない
- ルートロガーを変更しない
- ファイルハンドラーを追加しない
- ログフォーマットを強制しない

---

## パフォーマンスへの影響

### NullHandler のオーバーヘッド

```python
# 心配不要：NullHandler は何もしない（超高速）
logger.debug("message")  # 約 0.1μs（マイクロ秒）

# ログレベルでフィルタされるため、実質的にオーバーヘッドなし
```

### 文字列生成のコスト

```python
# ❌ 遅い（毎回文字列を生成）
logger.debug(f"Query: {expensive_operation()}")

# ✅ 速い（DEBUG レベルが有効な場合のみ実行）
logger.debug("Query: %s", expensive_operation())

# または
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Query: {expensive_operation()}")
```

---

## 関連リソース

### Python 公式ドキュメント
- [Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Configuring Logging for a Library](https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library)

### 参考実装
- SQLAlchemy: `sqlalchemy.engine` ロガー
- FastAPI: `fastapi` ロガー
- Requests: `requests` ロガー

### repom ドキュメント
- [セッション管理ガイド](../guides/session_management_guide.md)
- [BaseRepository ガイド](../guides/repository_and_utilities_guide.md)

---

## 実装スケジュール

### Phase 1: ロギングインフラ（今日）
- [ ] `repom/logging.py` 作成
- [ ] `tests/unit_tests/test_logging.py` 作成
- [ ] テスト実行・確認

### Phase 2: BaseRepository（今日）
- [ ] ログ追加
- [ ] 既存テストでの動作確認

### Phase 3: session.py（今日）
- [ ] ログ追加
- [ ] 既存テストでの動作確認

### Phase 4: ドキュメント（今日）
- [ ] `docs/guides/logging_guide.md` 作成
- [ ] `README.md` 更新
- [ ] コミット・プッシュ

---

## 検討すべき代替案（要議論）

### 代替案1: 環境変数で制御

```python
# repom/logging.py
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f'repom.{name}')
    
    # 環境変数 REPOM_AUTO_LOGGING=true の場合のみ自動設定
    if os.environ.get('REPOM_AUTO_LOGGING', '').lower() == 'true':
        if not repom_root_logger.handlers:
            # 自動設定を適用
            ...
    else:
        # NullHandler（従来の動作）
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
    
    return logger
```

**利点**:
- 明示的なオプトイン
- デフォルトは NullHandler（ライブラリの原則に準拠）

**欠点**:
- CLI ツールでも環境変数設定が必要
- ユーザーが設定を忘れる可能性

---

### 代替案2: 2つの関数を提供

```python
# repom/logging.py

def get_logger(name: str) -> logging.Logger:
    """NullHandler のみ（従来の動作）"""
    logger = logging.getLogger(f'repom.{name}')
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def get_logger_auto(name: str) -> logging.Logger:
    """自動設定付き（ハイブリッドアプローチ）"""
    logger = logging.getLogger(f'repom.{name}')
    
    if not _logger_initialized:
        # 自動設定を適用
        ...
    
    return logger
```

**利点**:
- ユーザーが選択できる
- 既存のコードは変更不要

**欠点**:
- CLI ツールで `get_logger_auto()` を使う必要がある
- 2つの関数を保守する必要がある

---

### 代替案3: NullHandler + 推奨設定を提供

```python
# repom/logging.py

def get_logger(name: str) -> logging.Logger:
    """NullHandler のみ"""
    logger = logging.getLogger(f'repom.{name}')
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def setup_logging() -> None:
    """推奨されるログ設定を適用（オプション）"""
    from repom.config import config
    
    repom_root_logger = logging.getLogger('repom')
    repom_root_logger.setLevel(logging.DEBUG)
    
    # FileHandler を追加
    file_handler = logging.FileHandler(config.log_file_path, encoding='utf-8')
    file_handler.setFormatter(...)
    repom_root_logger.addHandler(file_handler)
    
    # コンソール出力を追加
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(...)
    repom_root_logger.addHandler(console_handler)
```

```python
# repom/scripts/db_create.py
from repom.logging import setup_logging, get_logger

# CLI ツールでは明示的に呼ぶ
setup_logging()

logger = get_logger(__name__)
logger.info("Creating database...")
```

**利点**:
- ライブラリの原則に準拠（NullHandler）
- 明示的な設定呼び出し

**欠点**:
- すべての CLI ツールで `setup_logging()` を呼ぶ必要がある
- 呼び忘れのリスク

---

## 次のステップ（要議論）

### 実装前に議論すべき項目

1. **ハイブリッドアプローチの是非**
   - このアプローチで進めるべきか？
   - 代替案の方が良いか？

2. **懸念点への対処**
   - テスト時の動作はどうすべきか？
   - ルートロガーのハンドラー判定は十分か？

3. **ドキュメント化**
   - ユーザーにどう説明するか？
   - ベストプラクティスは何か？

4. **テスト戦略**
   - どのようにテストするか？
   - エッジケースは何か？

### 実装スケジュール（決定後）

### Phase 1: ロギングインフラ（今日）
- [x] 設計の最終決定
- [x] `repom/logging.py` 実装
- [x] `tests/unit_tests/test_logging.py` 作成
- [x] テスト実行・確認

### Phase 2: BaseRepository（将来）
- [ ] ログ追加
- [ ] 既存テストでの動作確認

### Phase 3: session.py（将来）
- [ ] ログ追加
- [ ] 既存テストでの動作確認

### Phase 4: ドキュメント（今日）
- [x] `docs/guides/logging_guide.md` 作成
- [x] `README.md` 更新
- [x] コミット・プッシュ

---

## 実装結果（2025-01-XX）

### 完了した内容

**Phase 1: ロギングインフラ構築**

✅ **repom/logging.py 実装完了**
- `get_logger()` 関数を実装
- ハイブリッドアプローチの動作確認
- CLI ツール実行時: `config.log_file_path` + コンソール
- アプリ側: `logging.basicConfig()` 優先

✅ **tests/unit_tests/test_logging.py 作成完了**
- 6つのテストケース作成
- デフォルト設定、basicConfig 優先、ハンドラー判定をテスト
- 全テスト成功（223 passed）

✅ **docs/guides/logging_guide.md 作成完了**
- CLI ツール実行時のログ
- アプリケーション使用時のログ
- config_hook でのカスタマイズ
- テスト時のログ制御
- トラブルシューティング
- 実例を豊富に提供

✅ **README.md 更新完了**
- ロギングガイドへのリンク追加

### テスト結果

```bash
# repom/tests/unit_tests/test_logging.py
6 passed

# 全ユニットテスト
223 passed
```

### 今後の予定

**Phase 2: BaseRepository へのログ追加**（別 Issue で対応）
- `get_by_id()`, `find()`, `save()`, `delete()` にログ追加
- デバッグ、情報、警告、エラーのログレベル設定

**Phase 3: session.py へのログ追加**（別 Issue で対応）
- トランザクション開始、コミット、ロールバックのログ追加

---

最終更新: 2025-01-XX
