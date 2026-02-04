　# Issue #028: テストアーキテクチャの複雑性（親Issue）

**ステータス**: 🔄 作業中

**作成日**: 2026-02-01

**最終更新**: 2026-02-04

**優先度**: 中

---

## 概要

テストアーキテクチャに関する複数の問題を統合的に管理する親Issue。
各問題は独立したサブIssueとして分離し、段階的に改善する。

---

## サブIssue

| ID | タイトル | 優先度 | 複雑度 | ステータス | 推奨順序 |
|----|---------|--------|--------|-----------|----------|
| [#034](034_remove_autouse_from_fixtures.md) | autouse=True の削除 | 高 | 低 | 🔴 未着手 | **1. 最優先** |
| [#035](035_separate_sqlite_postgres_fixtures.md) | SQLite/PostgreSQL Fixture 分離 | 中 | 中 | 🔴 未着手 | 2. 次のステップ |
| [#036](036_fixture_scope_review.md) | Fixture Scope 見直し | 低 | 高 | 🟡 提案中 | 3. 要検討 |

---

## Phase 構成

### Phase 1: PostgreSQL設定統合 ✅ **完了**
- **Issue #027** (完了): PostgreSQL設定統合
- config.db_type による PostgreSQL/SQLite 切り替え
- 環境変数削除、統合テストの安定化

### Phase 2: Fixture の改善 🔴 **次のフェーズ**
- **Issue #034** (未着手): autouse=True 削除
  - 不要なsetup実行を削減
  - パフォーマンス向上
  - テストの意図を明確化

- **Issue #035** (未着手): SQLite/PostgreSQL fixture 分離
  - 条件分岐の削減
  - 可読性・メンテナンス性向上
  - DB固有の要件を分離

### Phase 3: Scope の見直し 🟡 **要検討**
- **Issue #036** (提案中): Fixture scope 見直し
  - 調査フェーズから開始
  - パフォーマンス影響を評価
  - 必要性を精査

---

## 問題の概要

現在のテスト構造は、デフォルトでSQLiteを使用し、PostgreSQLテスト時に動作を変更する必要があるため、複雑になっている。

## 現在の問題点

### 1. **conftest.py の複雑な条件分岐**

```python
# tests/conftest.py (line 6)
os.environ['EXEC_ENV'] = 'test'  # ハードコード

# setup_repom_db_tables fixture (lines 33-90)
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    # 問題1: no_db_setup マーカーのチェック（使われていない）
    if request.node.get_closest_marker('no_db_setup'):
        yield
        return
    
    # 問題2: PostgreSQL特有の条件分岐
    if not (db_type == 'postgres' and exec_env == 'dev'):
        # async engine 作成
```

**問題**:
- `autouse=True` で全テストに強制適用
- PostgreSQL と SQLite の混在で条件が複雑化
- session scope なのに個別テストで制御不可

### 2. **環境変数の上書き合戦**

```python
# tests/conftest.py (line 6)
os.environ['EXEC_ENV'] = 'test'

# tests/integration_tests/conftest.py (line 8)
os.environ['EXEC_ENV'] = 'dev'  # 上書き

# tests/integration_tests/test_postgres_integration.py (line 7)
os.environ['EXEC_ENV'] = 'dev'  # 念のため再上書き

# tests/unit_tests/test_config_postgres.py (line 13)
if 'DB_TYPE' in os.environ:
    del os.environ['DB_TYPE']  # クリア
```

**問題**:
- 環境変数の上書きが複数箇所で発生
- どの設定が最終的に適用されるか不明瞭
- テスト実行順序に依存する可能性

### 3. **矛盾したテスト設計**

```python
# tests/unit_tests/test_config_postgres.py
# PostgreSQL config のテストなのに SQLite 環境で実行
if 'DB_TYPE' in os.environ:
    del os.environ['DB_TYPE']  # PostgreSQL設定をテストしたいのに削除
```

**問題**:
- PostgreSQL プロパティをテストするのに SQLite 環境
- 実際の使用シナリオと乖離

### 4. **fixture の重複と衝突**

```python
# tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    # SQLite 前提の実装

# tests/integration_tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_postgres_tables():
    # PostgreSQL 前提の実装（実際には使われていない）
```

**問題**:
- 両方 autouse=True なので両方実行される
- PostgreSQL 統合テスト時に親の fixture が先に実行される
- 子の fixture が実質的に意味をなさない

## 根本原因と分離理由

### 1. **autouse=True の濫用** → **Issue #034**
- 全テストで不要な setup が実行される
- DB接続を必要としないテストでも DB setup が実行される
- テストごとに制御不可

**独立性**: ✅ 他の問題と無関係に解決可能
**リスク**: 低（fixture内容は変更しない）
**効果**: パフォーマンス向上、意図の明確化

### 2. **SQLite/PostgreSQLの混在** → **Issue #035**
- 単一の conftest.py で全てを制御しようとしている
- SQLite と PostgreSQL で異なる要件があるのに同じ fixture
- 条件分岐が複雑化

**独立性**: ✅ Issue #034後に実装推奨
**リスク**: 中（fixture構造変更）
**効果**: 可読性・メンテナンス性向上

### 3. **session scope の制約** → **Issue #036**
- 一度初期化したら変更できない
- 環境切り替え不可
- テストごとの柔軟性なし

**独立性**: ✅ 独立して実装可能だが要調査
**リ実装推奨順序

### ステップ1: Issue #034（最優先）

**autouse=True の削除**

理由:
- 低リスク・高効果
- 他のIssueの前提となる改善
- パフォーマンス向上が期待できる

実装内容:
- `setup_repom_db_tables` から autouse=True を削除
- 必要なテストに明示的にfixture指定
- 不要な `@pytest.mark.no_db_setup` マーカー削除

見積もり: 55分

### ステップ2: Issue #035（次のステップ）

**SQLite/PostgreSQL Fixture 分離**

理由:
- Issue #034完了後に実装するとスムーズ
- 条件分岐を大幅に削減
- 可読性・メンテナンス性が向上

実装内容:
- `setup_sqlite_tables` 作成
- `setup_postgres_tables` 作成
- 後方互換性のための `setup_db_tables` エイリアス
- 複雑な条件分岐を削除

見積もり: 90分

### ステップ3: Issue #036（要検討）

**Fixture Scope 見直し**

理由:
- 調査が必要（パフォーマンス影響の評価）
- 現状で大きな問題がない
- 必要性を精査してから実装判断

実装内容:
- 調査フェーズ（60分）
- 必要に応じて実装（60分+）

見積もり: 120分+（調査含む）

---

## 推奨実装プラン

### Phase 2-A: Issue #034 実装
1. autouse=True 削除
2. テストにfixture追加
3. 全テスト検証

### Phase 2-B: Issue #035 実装
1. fixture分離
2. 条件分岐削除
3. 全テスト検証

### Phase 3: Issue #036 調査・検討
1. パフォーマンス測定
2. 必要性評価
3. 実装判断

---

## 次のアクション

1. **Issue #034 の実装開始**（承認後）
2. 完了後、Issue #035 の実装
3. Issue #036 は調査フェーズから開始autouse=False) の組み合わせ**

理由:
1. 環境変数のハードコードを排除
2. fixture を必要なテストでのみ使用
3. 既存のディレクトリ構造を維持
4. pytest 標準機能で実装

実装ステップ:
1. pytest_configure で環境変数を設定
2. setup_repom_db_tables を autouse=False に変更
3. 必要なテストファイルでのみ fixture を明示的に使用
4. 環境変数の上書きコードを削除

## 次のアクション

1. ユーザーに推奨案を提示
2. 承認後、Issue #029 として実装開始
3. 段階的リファクタリング（既存テストを壊さない）

## 関連Issue

- Issue #026: PostgreSQL Docker セットアップ (完了)
- Issue #027: PostgreSQL 設定切り替え対応 (完了)
- Issue #029: テストアーキテクチャのリファクタリング (提案中)
