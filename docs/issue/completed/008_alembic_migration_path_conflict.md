# Issue #8: Alembic マイグレーションファイルの保存場所制御

**ステータス**: ✅ 完了

**作成日**: 2025-11-16

**完了日**: 2025-11-16

**優先度**: 高

**複雑度**: 中

---

## 問題の説明

外部プロジェクト（mine-py など）で repom を使用する際、マイグレーションファイルの保存場所を制御できず、repom の `alembic/versions/` にファイルが作成されてしまう問題。

**エラー例**:
```
ERROR [alembic.util.messaging] Can't locate revision identified by '817393cd599a'
```

**根本原因**:
- Alembic の `alembic revision` コマンドは CLI レベルで ScriptDirectory を初期化
- env.py が呼ばれる時点では既に `version_locations` が確定済み
- env.py での動的設定は**ファイル作成に間に合わない**

**詳細な技術調査**: `docs/technical/alembic_version_locations_limitation.md` 参照

---

## 最終的な解決策

### alembic.ini を唯一の設定源とする

**方針**: ファイル作成と実行の両方で `alembic.ini` の `version_locations` を使用。

**理由**:
- env.py での動的設定はファイル作成に効かない（Alembic の制約）
- 設定が1箇所だけなので混乱がない
- 標準的な Alembic の使い方

### 実装内容

#### repom の設定

```ini
# repom/alembic.ini
[alembic]
script_location = alembic
version_locations = alembic/versions
```

```python
# repom/alembic/env.py
# version_locations は alembic.ini から自動的に読み込まれる
# 動的設定は削除（効果がないため）
```

#### 外部プロジェクトの設定

```ini
# mine-py/alembic.ini（必須）
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

### 変更内容

1. **env.py から削除**:
   - `config.set_main_option("version_locations", ...)` - ファイル作成に効かない
   - `context.configure(version_locations=...)` - 実行時は alembic.ini から自動読み込み

2. **config.py から削除**:
   - `_alembic_versions_path` フィールド - 不要になった
   - `alembic_versions_path` プロパティ - 不要になった

3. **alembic.ini に追加**:
   - `version_locations = alembic/versions` - 明示的に記述

---

## 断念した代替案

### 案1: MineDbConfig で動的制御

```python
# 試みた方法
config._alembic_versions_path = '/custom/path'
```

**断念理由**: env.py が呼ばれる時点で ScriptDirectory は既に初期化済み。

### 案2: 独自 CLI コマンド

```bash
poetry run repom-revision -m "message"
```

**断念理由**: 標準的な Alembic の使い方から逸脱。保守コストが高い。

---

## 動作確認

### repom 単体

```bash
poetry run alembic revision -m "test"
# → alembic/versions/ に作成 ✅
```

### 外部プロジェクト（mock_external_project）

```bash
cd tests/integration_tests/mock_external_project
poetry run alembic revision -m "test"
# → mock_external_project/alembic/versions/ に作成 ✅
```

---

## 関連ドキュメント

- **技術調査**: `docs/technical/alembic_version_locations_limitation.md`
- **ユーザーガイド**: `README.md#alembic-マイグレーション`
- **開発者ガイド**: `AGENTS.md#alembic-configuration`

---

**完了**: 2025-11-16  
**実装**: alembic.ini ベースの設定に統一
