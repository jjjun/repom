# Issue #8: Alembic マイグレーションパス競合問題

**ステータス**: 🟢 進行中

**作成日**: 2025-11-16

**優先度**: 高

**複雑度**: 中

## 問題の説明

repom の `alembic/env.py` が `script_location` と `version_locations` を動的に上書きすることで、外部プロジェクトのマイグレーション管理と競合し、マイグレーションが失敗する。

**エラー例**:
```
ERROR [alembic.util.messaging] Can't locate revision identified by '817393cd599a'
```

**根本原因**:
- `env.py` が `config.set_main_option("version_locations", ...)` で repom のパスを設定
- 外部プロジェクトの `alembic/versions/` が参照されない
- マイグレーション履歴が repom と外部プロジェクトで分散

## 採用する設計方針

### 方針 A: MineDbConfig による完全制御 + 最小限の alembic.ini

**基本方針**:
1. **MineDbConfig でパス制御**: 外部プロジェクトは `MineDbConfig` を継承して `alembic_versions_path` を設定
2. **最小限の alembic.ini**: 3行のみ（`script_location` のみ設定）
3. **env.py が動的設定**: `version_locations` を `MineDbConfig` から取得して設定

**実装イメージ**:

```python
# repom/config.py
@property
def alembic_versions_path(self) -> str:
    if self._alembic_versions_path is not None:
        return self._alembic_versions_path
    # デフォルト: repom のディレクトリ
    return str(Path(self.root_path) / 'alembic' / 'versions')
```

```python
# repom/alembic/env.py
from repom.config import config as db_config

# MineDbConfig から動的に設定（CONFIG_HOOK で外部設定が注入される）
config.set_main_option("sqlalchemy.url", db_config.db_url)
config.set_main_option("version_locations", db_config.alembic_versions_path)
# script_location は alembic.ini で静的に設定（上書きしない）
```

```ini
# repom/alembic.ini（repom 単体用）
[alembic]
script_location = alembic
```

```ini
# mine-py/alembic.ini（外部プロジェクト用・最小限）
[alembic]
script_location = submod/repom/alembic
```

```python
# mine-py/src/mine_py/config.py
class MinePyConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        project_root = Path(__file__).parent.parent.parent
        self._alembic_versions_path = str(project_root / 'alembic' / 'versions')
```

**動作フロー**:
```
mine-py で: poetry run alembic upgrade head
    ↓
[1] mine-py/alembic.ini を読み込み → script_location = submod/repom/alembic
    ↓
[2] submod/repom/alembic/env.py を実行
    ↓
[3] CONFIG_HOOK が MinePyConfig を読み込み
    ↓
[4] env.py が version_locations = mine-py/alembic/versions を設定
    ↓
[5] mine-py/alembic/versions/ のマイグレーションを実行
```

**メリット**:
- 標準的な Alembic コマンドが使える
- 外部プロジェクトは `MineDbConfig` を継承するだけ
- `alembic.ini` は最小限（3行）
- CONFIG_HOOK の仕組みを活用

## 実装計画

### Phase 1: config.py のシンプル化 ✅ **完了**
- [x] `_alembic_path` フィールドを削除（不要な中間レイヤーの排除）
- [x] `alembic_path` プロパティ/セッターを削除
- [x] `alembic_versions_path` プロパティをシンプル化（デフォルト値を直接計算）
- [x] `init()` から `alembic_path` のパス作成を削除
- [x] テストの更新（`test_alembic_config.py` から alembic_path 関連の3テストを削除）
- [x] 全テストパス確認（191 passed, 1 skipped）

**実装結果**: 
- `repom/config.py`: `_alembic_path` を完全削除、`alembic_versions_path` は `_alembic_versions_path` から直接計算
- `tests/unit_tests/test_alembic_config.py`: 6テストのみ残存（alembic_versions_path 関連のみ）
- 外部プロジェクトは `_alembic_versions_path` を直接設定すれば良い（よりシンプルに）

### Phase 2: alembic/env.py の修正
- [x] `script_location` の上書きを削除（alembic.ini の設定を使用）
- [x] `version_locations` を `MineDbConfig.alembic_versions_path` から動的設定
- [x] コメントで理由を説明

### Phase 3: alembic.ini を最小限に修正
- [x] repom: `script_location = alembic` のみ（version_locations はコメントアウト）
- [ ] 外部プロジェクト用テンプレート作成

### Phase 4: テストの作成と実行
- [x] `test_alembic_config.py` - MineDbConfig のパス設定テスト（6テスト）
- [ ] `test_alembic_integration.py` - Alembic コマンドの統合テスト
- [x] 既存のユニットテストがパスすることを確認（191 passed, 1 skipped）

### Phase 5: ドキュメント更新 ✅ **完了**
- [x] README.md - マイグレーション手順（Alembic 設定のカスタマイズセクション追加）
- [x] AGENTS.md - プロジェクト構造と設定（Alembic Configuration セクション追加）
- [x] .github/copilot-instructions.md - AI への指示（Alembic Configuration ガイドライン追加）
- [ ] ideas/alembic_version_location_configuration.md を completed に移動

**更新内容**:
- `MineDbConfig.alembic_versions_path` によるマイグレーションファイル位置制御の説明
- 外部プロジェクト向けのセットアップ手順（3ステップ）
- CONFIG_HOOK を使った設定注入パターンの解説
- 最小限の alembic.ini（3行のみ）の例

### Phase 6: 外部プロジェクトへの対応
- [ ] mine-py での動作確認
- [ ] 移行ガイドの作成

## テスト計画

### Unit Tests (pytest で完全自動化)

```python
# tests/unit_tests/test_alembic_config.py
def test_alembic_versions_path_default():
    """デフォルトのパスが正しいことを確認"""
    
def test_alembic_versions_path_custom():
    """カスタムパスが設定できることを確認"""

def test_alembic_versions_path_inheritance():
    """継承でパスを上書きできることを確認"""
```

### Integration Tests

```python
# tests/unit_tests/test_alembic_integration.py
def test_alembic_revision_creates_file(tmp_path):
    """マイグレーションファイルが指定ディレクトリに生成されることを確認"""

def test_alembic_upgrade_applies_migrations(tmp_path, db_session):
    """マイグレーションが正しく適用されることを確認"""
```

## 外部プロジェクト移行ガイド

### 最小限の設定（mine-py の例）

```ini
# mine-py/alembic.ini（3行のみ）
[alembic]
script_location = submod/repom/alembic
```

```python
# mine-py/src/mine_py/config.py
from repom.config import MineDbConfig
from pathlib import Path

class MinePyConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        project_root = Path(__file__).parent.parent.parent
        self._alembic_versions_path = str(project_root / 'alembic' / 'versions')

# CONFIG_HOOK で repom に注入
def get_repom_config():
    return MinePyConfig()
```

### マイグレーション実行

```powershell
# 標準的な Alembic コマンドがそのまま使える
poetry run alembic upgrade head
poetry run alembic revision --autogenerate -m "add user table"
```

## 関連ドキュメント

- `docs/ideas/alembic_version_location_configuration.md` - 元のアイデア
- `alembic.ini`, `alembic/env.py` - 実装対象
- `README.md`, `AGENTS.md` - 更新予定

---

**担当者**: GitHub Copilot  
**関連 Ideas**: `docs/ideas/alembic_version_location_configuration.md`
