# Alembic version_locations の制約と将来的な改善案

## 問題の概要

**Issue Date**: 2025-11-16

Alembic でマイグレーションファイルの保存場所を動的に制御しようとした際、`alembic.ini` に `version_locations` を記述しなければファイル作成場所を制御できないことが判明しました。

### 理想的な動作

```python
# 理想: config.py だけで制御したい
class MinePyConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        self._alembic_versions_path = '/custom/path/versions'
```

このように Python コードだけで設定し、外部プロジェクトは `alembic.ini` を配置せずに済むのが理想的です。

### 現実の制約

```ini
# 現実: alembic.ini に必ず記述が必要
[alembic]
version_locations = %(here)s/alembic/versions
```

**結論**: 現在の Alembic の実装では、`alembic.ini` への記述が**必須**です。

---

## 技術的な根本原因

### Alembic のコマンド実行フロー

#### 1. ファイル作成フェーズ (`alembic revision`)

```
┌─────────────────────────────────────────┐
│ 1. CLI が alembic.ini を読み込み       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ 2. ScriptDirectory を初期化             │
│    ← この時点で version_locations 確定  │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ 3. env.py を実行（autogenerate のみ）  │
│    ← もう手遅れ！                       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ 4. マイグレーションファイルを生成       │
└─────────────────────────────────────────┘
```

**問題点**: `env.py` が実行される時点で、既に `ScriptDirectory` は初期化済みであり、`version_locations` は確定しています。

#### 2. マイグレーション実行フェーズ (`alembic upgrade`)

```
┌─────────────────────────────────────────┐
│ 1. CLI が alembic.ini を読み込み       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ 2. env.py を実行                        │
│    ← context.configure() が呼ばれる     │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ 3. マイグレーションファイルを読み込み   │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ 4. マイグレーションを実行               │
└─────────────────────────────────────────┘
```

**ポイント**: 実行フェーズでは `context.configure(version_locations=...)` が有効ですが、ファイル作成フェーズには影響しません。

---

## 実験結果

### 実験1: `config.set_main_option()` の効果

```python
# env.py で設定してみる
config = Config("alembic.ini")
config.set_main_option("version_locations", "/custom/path")
script = ScriptDirectory.from_config(config)
print(script.version_locations)  # → ['/custom/path'] ✅
```

**結果**: ✅ **ScriptDirectory に影響する** - ScriptDirectory 作成**後**に設定すれば有効

### 実験2: `alembic revision` コマンドでは？

```bash
# env.py で config.set_main_option() を呼んでいる状態で:
poetry run alembic revision -m "test"
# → repom/alembic/versions/ に作成される ❌
```

**結果**: ❌ **効果なし** - CLI が ScriptDirectory を初期化**してから** env.py を呼ぶため

### 実験3: `alembic.ini` に記述した場合

```ini
# alembic.ini
[alembic]
version_locations = custom/path/versions
```

```bash
poetry run alembic revision -m "test"
# → custom/path/versions/ に作成される ✅
```

**結果**: ✅ **正常動作** - CLI が ScriptDirectory 初期化**前**に読み込むため

---

## Alembic ソースコード分析

### ScriptDirectory 初期化のタイミング

```python
# alembic/command.py (簡略版)
def revision(config, message=None, autogenerate=False, ...):
    # 1. ScriptDirectory を初期化（ここで version_locations 確定）
    script = ScriptDirectory.from_config(config)
    
    # 2. autogenerate の場合のみ env.py を実行
    if autogenerate:
        run_env(config, script)  # ← env.py がここで呼ばれる
    
    # 3. ファイルを生成（version_locations は既に確定済み）
    script.generate_revision(...)
```

### ScriptDirectory.from_config() の処理

```python
# alembic/script/base.py (簡略版)
@classmethod
def from_config(cls, config):
    # alembic.ini から version_locations を読み取る
    version_locations = config.get_main_option("version_locations")
    
    # ScriptDirectory を作成
    return cls(
        dir=script_location,
        version_locations=version_locations.split(os.pathsep) if version_locations else None
    )
```

**重要**: `from_config()` の時点で `version_locations` は確定し、後から変更できません。

---

## 現在の実装と制約

### repom の実装（2025-11-16 時点）

```ini
# repom/alembic.ini
[alembic]
script_location = alembic
version_locations = alembic/versions
```

```python
# repom/alembic/env.py
# version_locations は alembic.ini から読み取るのみ
# 動的設定は行わない（効果がないため）
```

### 外部プロジェクトの実装

```ini
# mine-py/alembic.ini（必須）
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

**制約**: 外部プロジェクトは必ず `alembic.ini` を配置する必要があります。

---

## 将来的な改善案

### 案1: Alembic 本体の改善を待つ

**理想的な動作**:

```python
# env.py で動的設定が効くようになってほしい
config.set_main_option("version_locations", custom_path)
# ↑ これが alembic revision でも効くようになれば解決
```

**必要な変更** (Alembic 側):

```python
# alembic/command.py
def revision(config, ...):
    # env.py を先に実行して設定を適用
    if autogenerate:
        run_env(config, None)  # script を渡さない
    
    # その後 ScriptDirectory を初期化
    script = ScriptDirectory.from_config(config)
    # ↑ この順序なら env.py の設定が反映される
```

**メリット**:
- ✅ Python コードだけで完結
- ✅ 外部プロジェクトが `alembic.ini` を持つ必要がない
- ✅ 動的な設定が可能

**デメリット**:
- ❌ Alembic 本体の変更が必要
- ❌ env.py を常に実行するためパフォーマンス影響あり

### 案2: 独自 CLI コマンドを作成

```python
# repom/scripts/repom_revision.py
from alembic.config import Config
from alembic import command
from repom.config import config as db_config

def main():
    config = Config("alembic.ini")
    # CLI レベルで version_locations を設定
    config.set_main_option("version_locations", db_config.alembic_versions_path)
    command.revision(config, message="...", autogenerate=True)

# pyproject.toml
[tool.poetry.scripts]
repom-revision = "repom.scripts.repom_revision:main"
```

**使い方**:

```bash
# 標準の alembic コマンドの代わりに
poetry run repom-revision -m "add column"
```

**メリット**:
- ✅ Python コードだけで設定可能
- ✅ Alembic 本体の変更不要
- ✅ 今すぐ実装可能

**デメリット**:
- ❌ 標準的な Alembic の使い方から逸脱
- ❌ 独自コマンドの保守が必要
- ❌ すべての `alembic` コマンドをラップする必要がある

### 案3: Alembic の `process_revision_directives` を活用

```python
# env.py
def process_revision_directives(context, revision, directives):
    # ファイル生成時にパスを変更できる可能性を調査
    # （現在の Alembic API では不可能だが、将来的に？）
    pass
```

**現状**: このコールバックではファイル内容を変更できますが、保存場所は変更できません。

---

## 推奨アプローチ

### 短期的（現在）

**案1** を採用: Alembic の標準的な使い方に従い、`alembic.ini` に記述する。

```ini
# External project: mine-py/alembic.ini
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

**理由**:
- 標準的で理解しやすい
- Alembic のドキュメントに沿っている
- トラブルが少ない

### 長期的（将来）

Alembic のコミュニティに以下を提案:

1. **Feature Request**: `env.py` での動的設定をサポート
2. **Issue 作成**: ScriptDirectory 初期化タイミングの問題を報告
3. **PR 提出**: 実装案を提案

**提案内容**:

```python
# 新しい設定オプション
[alembic]
defer_script_directory_init = true  # env.py を先に実行

# または新しい API
config.set_version_locations_deferred(lambda: custom_path)
```

---

## 関連リソース

### Alembic 公式ドキュメント

- [Configuration File](https://alembic.sqlalchemy.org/en/latest/tutorial.html#editing-the-ini-file)
- [Multiple Version Directories](https://alembic.sqlalchemy.org/en/latest/branches.html#working-with-multiple-bases)
- [Runtime Objects](https://alembic.sqlalchemy.org/en/latest/api/runtime.html)

### repom ドキュメント

- [Alembic Architecture Guide](../guides/alembic_architecture_and_version_locations.md)
- [README.md - Alembic Configuration](../../README.md#alembic-configuration)
- [AGENTS.md - Alembic Configuration](../../AGENTS.md#alembic-configuration)

### 関連 Issue

- repom Issue #8: Alembic マイグレーションファイルの保存場所制御
- [完了済み](../issue/completed/) - 2025-11-16

---

## まとめ

### 現状の制約

| 項目 | ファイル作成 | マイグレーション実行 |
|------|-------------|---------------------|
| **制御方法** | `alembic.ini` のみ | `alembic.ini` または `env.py` |
| **env.py の効果** | ❌ 無効 | ✅ 有効 |
| **動的設定** | ❌ 不可能 | ✅ 可能 |

### 理想の動作（将来）

| 項目 | ファイル作成 | マイグレーション実行 |
|------|-------------|---------------------|
| **制御方法** | `env.py` で設定可能 | `env.py` で設定可能 |
| **alembic.ini** | 最小限（script_location のみ） | 最小限 |
| **動的設定** | ✅ 可能 | ✅ 可能 |

### アクションアイテム

- [x] ドキュメント作成（このファイル）
- [ ] Alembic コミュニティに Feature Request を提出
- [ ] Alembic の最新版で改善されているか定期的にチェック
- [ ] 必要に応じて独自 CLI コマンドの実装を検討

---

**Last Updated**: 2025-11-16  
**Status**: 現在の実装は `alembic.ini` ベース、将来的な改善を期待
