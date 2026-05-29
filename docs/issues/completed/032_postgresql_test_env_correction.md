# Issue #032: PostgreSQL 統合テストの EXEC_ENV 修正

**ステータス**: 🔴 未着手

**作成日**: 2026-02-04

**優先度**: 高

**複雑度**: 低

---

## 問題の説明

PostgreSQL 統合テストが `EXEC_ENV='dev'` を使用しているが、これには明確な理由がない。

### 現状

```python
# tests/integration_tests/conftest.py (line 8)
os.environ['EXEC_ENV'] = 'dev'

# tests/integration_tests/test_postgres_integration.py (line 8)
os.environ['EXEC_ENV'] = 'dev'
```

これにより、PostgreSQL データベース名が `repom_dev` になる：

```python
# repom/config.py の postgres_db プロパティ
if env == 'test':
    return f"{base}_test"      # repom_test
elif env == 'dev':
    return f"{base}_dev"       # repom_dev ← 現在これを使用
elif env == 'prod':
    return base
```

### 問題点

1. **テストなのに `test` 環境を使わない矛盾**
   - テストコードが開発環境（`dev`）を使用している
   - 意味的に不自然

2. **設計意図が不明瞭**
   - `repom_dev` を使う明確な理由が存在しない
   - 歴史的経緯で放置された可能性

3. **環境の混乱を招く**
   - テストなのに `dev` 環境という混乱
   - 新しい開発者が理解しにくい

### 根本原因

- 最初に PostgreSQL テストを追加した際に `repom_dev` を使ってしまった
- **確認済み**: `repom_test` データベースは既に `repom/postgres/init.template/01_init_databases.sql` で作成されている
- 環境変数の上書きが残っているだけ

---

## 期待される動作

PostgreSQL 統合テストは **`EXEC_ENV='test'`** を使用し、**`repom_test`** データベースに接続する。

```python
# tests/integration_tests/conftest.py
# EXEC_ENV='test' のまま（親の conftest.py の設定を上書きしない）

# tests/integration_tests/test_postgres_integration.py
# EXEC_ENV の上書きを削除
```

結果:
- PostgreSQL URL: `postgresql://repom:repom_dev@localhost:5432/repom_test`
- 意味的に正しい（テストは test 環境を使用）
- 環境変数の上書きが1つ減る

---

## 提案される解決策

### ✅ 前提: `repom_test` データベースは既に存在

**確認済み**: `repom/postgres/init.template/01_init_databases.sql` で既に作成されている

```sql
-- テスト環境用
CREATE DATABASE repom_test;
GRANT ALL PRIVILEGES ON DATABASE repom_test TO repom;
```

Docker の修正は**不要**。テストコードの環境変数のみ修正すればよい。

### 1. 環境変数の上書きを削除

**ファイル**: `tests/integration_tests/conftest.py`

```python
# 削除（または行ごと削除）
# os.environ['EXEC_ENV'] = 'dev'
```

**ファイル**: `tests/integration_tests/test_postgres_integration.py`

```python
# 削除
# os.environ['EXEC_ENV'] = 'dev'
```

### 2. conftest.py の条件分岐を修正

**ファイル**: `tests/conftest.py`

```python
# 変更前
if not (config.db_type == 'postgres' and exec_env == 'dev'):

# 変更後
if not (config.db_type == 'postgres' and exec_env == 'test'):
```

---

## 影響範囲

### 変更が必要なファイル

1. **tests/integration_tests/conftest.py**
   - `os.environ['EXEC_ENV'] = 'dev'` の削除

2. **tests/integration_tests/test_postgres_integration.py**
   - `os.environ['EXEC_ENV'] = 'dev'` の削除

3. **tests/conftest.py**
   - 条件分岐の修正（`exec_env == 'dev'` → `exec_env == 'test'`）

### 影響を受けるテスト

- `tests/integration_tests/test_postgres_integration.py` の全テスト
  - PostgreSQL 統合テスト（7テスト）
  - **期待**: 全テストがパスし続ける（接続先が `repom_test` に変わるだけ）

### リスク

- **低リスク**: データベース名が変わるだけで、テストロジックは変わらない
- **事前確認**: `repom_test` データベースが正しく作成されることを確認

---

## 実装計画

### Phase 1: テストコードの修正（5分）

1. **tests/integration_tests/conftest.py を修正**
   - `os.environ['EXEC_ENV'] = 'dev'` の行を削除

2. **tests/integration_tests/test_postgres_integration.py を修正**
   - `os.environ['EXEC_ENV'] = 'dev'` の行を削除

3. **tests/conftest.py を修正**
   - 条件分岐を `exec_env == 'test'` に変更

### Phase 2: テストとバリデーション（5分）

4. **PostgreSQL 統合テストを実行**
   ```bash
   poetry run pytest tests/integration_tests/test_postgres_integration.py -v
   ```
   - 期待: 7テスト全てパス

5. **全テストを実行**
   ```bash
   poetry run pytest tests/unit_tests/
   poetry run pytest tests/behavior_tests/
   ```
   - 期待: 既存テストが壊れていないことを確認

**総見積もり**: 10分

---

## テスト計画

### 1. 接続テスト

```python
# tests/integration_tests/test_postgres_integration.py
def test_database_name():
    """接続先データベース名が repom_test であることを確認"""
    from repom.config import config
    assert config.postgres_db == 'repom_test'
```

### 2. 既存テストの回帰テスト

- PostgreSQL 統合テスト全7テストがパス
- Unit テスト全てがパス
- Behavior テスト全てがパス

---

## 完了基準

- ✅ `tests/integration_tests/conftest.py` から `EXEC_ENV='dev'` の行が削除されている
- ✅ `tests/integration_tests/test_postgres_integration.py` から `EXEC_ENV='dev'` の行が削除されている
- ✅ `tests/conftest.py` の条件分岐が `exec_env == 'test'` に修正されている
- ✅ PostgreSQL 統合テスト（7テスト）が全てパスする
- ✅ 全 Unit/Behavior テストがパスする（回帰なし）
- ✅ `config.postgres_db` が `repom_test` を返すことを確認

---

## 関連 Issue

- **Issue #028**: テストアーキテクチャの複雑性（親Issue）
- **Issue #027**: PostgreSQL 設定統合（完了済み）
- **Issue #033**: config 直接設定の削除（バグ修正、並行作業）

---

## 備考

### なぜこの修正が必要か

1. **意味的な正しさ**
   - テストは `test` 環境で実行すべき
   - 開発環境（`dev`）を使う理由がない

2. **メンテナンス性の向上**
   - 環境変数の上書きが減る
   - コードが理解しやすくなる

3. **Issue #028 の一環**
   - テストアーキテクチャの複雑性を解消する取り組み
   - 環境変数の上書き合戦を解消

### 優先度が高い理由

- **設計ミス**: テストが誤った環境を使用している
- **シンプルな修正**: 複雑な変更ではなく、環境変数削除のみ
- **低リスク**: データベース名が変わるだけで、既存のテストロジックは変わらない
- **Issue #033 との相乗効果**: 同時に修正することで環境変数管理がさらにクリーンになる

---

**最終更新**: 2026-02-04
