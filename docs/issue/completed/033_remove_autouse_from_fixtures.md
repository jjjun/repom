# Issue #034: autouse=True の削除

**ステータス**: 🔴 未着手

**作成日**: 2026-02-04

**優先度**: 高

**複雑度**: 低

**親Issue**: [Issue #028: テストアーキテクチャの複雑性](028_test_architecture_complexity.md)

---

## 問題の説明

現在、`tests/conftest.py` の `setup_repom_db_tables` フィクスチャが `autouse=True` で定義されており、**全テストで強制的に実行される**。

### 現状のコード

```python
# tests/conftest.py (line 34)
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    """全テスト実行前に自動実行される"""
    # engine作成
    # テーブル作成
    # ...
```

### 問題点

#### 1. **不要なテストでも実行される**

```python
# 例: configプロパティのみをテストする場合
def test_config_property():
    """DB接続不要なのにengine作成される"""
    from repom.config import config
    assert config.exec_env == 'test'
    # ↑ これだけなのに、setup_repom_db_tables が実行される
```

**影響**:
- テストが遅くなる（不要なengine作成）
- メモリ消費が増える
- デバッグが困難（なぜengine作成されたか不明）

#### 2. **テストごとに制御できない**

```python
# 特定のテストでDB setupをスキップしたい場合
@pytest.mark.no_db_setup  # ← マーカーが必要
def test_without_db():
    pass
```

**問題**:
- `autouse=True`なので全テストに強制適用
- スキップするには明示的にマーカー必要（逆転した設計）
- 「必要なテストでのみ使う」が正しいのに「不要なテストで除外する」になっている

#### 3. **意図が不明瞭**

```python
# 新しいテストを追加する際
def test_new_feature():
    """このテスト、何が起きてる？"""
    assert 1 + 1 == 2
    # ↑ setup_repom_db_tables が実行されていることに気づかない
```

---

## 期待される動作

fixture は**必要なテストでのみ明示的に使用する**べき。

### 正しいパターン

```python
# tests/conftest.py
@pytest.fixture(scope='session')  # autouse削除
def setup_repom_db_tables(request):
    """必要なテストでのみ明示的に使用"""
    # ...

# テストファイル
def test_with_db(setup_repom_db_tables, db_test):
    """DB必要なテスト：明示的にfixtureを指定"""
    repo = UserRepository(db_test)
    # ...

def test_without_db():
    """DB不要なテスト：fixtureを指定しない"""
    assert config.exec_env == 'test'
```

---

## 提案される解決策

### ステップ1: autouse=True を削除

```python
# tests/conftest.py
@pytest.fixture(scope='session')  # autouse削除
def setup_repom_db_tables(request):
    # ... 既存の実装を維持
```

### ステップ2: 必要なテストにfixtureを追加

DB接続が必要なテストファイルに明示的に追加：

```python
# tests/unit_tests/test_repository.py
def test_repository_operations(setup_repom_db_tables, db_test):
    # ...

# tests/behavior_tests/test_circular_import.py
def test_circular_import(setup_repom_db_tables, db_test):
    # ...
```

### ステップ3: 不要なマーカーを削除

`@pytest.mark.no_db_setup` マーカーは不要になるため削除：

```python
# 削除前
@pytest.mark.no_db_setup
def test_config():
    pass

# 削除後（fixture指定しないだけ）
def test_config():
    pass
```

---

## 影響範囲

### 変更が必要なファイル

1. **tests/conftest.py**
   - `setup_repom_db_tables` の `autouse=True` を削除

2. **DB接続が必要なテストファイル（推定50-100ファイル）**
   - fixture引数に `setup_repom_db_tables` を追加
   - ただし、多くのテストは既に `db_test` を使用しているため、実際の変更は少ない可能性

3. **tests/integration_tests/conftest.py**
   - `setup_postgres_tables` の `autouse=True` も削除を検討

### 影響を受けるテスト

- Unit tests: 約187テスト
- Behavior tests: 約8テスト
- Integration tests: 約8テスト（PostgreSQL）

**リスク評価**: 低
- 既存の動作を変えない（fixture内容は同じ）
- 明示的に指定するだけ

---

## 実装計画

### Phase 1: autouse削除とテスト確認（30分）

1. **tests/conftest.py を修正**
   ```python
   @pytest.fixture(scope='session')  # autouse削除
   def setup_repom_db_tables(request):
       # ...
   ```

2. **全テストを実行して失敗箇所を確認**
   ```bash
   poetry run pytest tests/unit_tests/ -v
   ```
   - 失敗するテスト = DB setupが必要なテスト

3. **失敗したテストにfixtureを追加**
   ```python
   def test_xxx(setup_repom_db_tables, db_test):
       # ...
   ```

### Phase 2: PostgreSQL統合テスト対応（15分）

4. **tests/integration_tests/conftest.py を修正**
   ```python
   @pytest.fixture(scope='session')  # autouse削除
   def setup_postgres_tables():
       # ...
   ```

5. **統合テストにfixtureを追加**
   ```bash
   poetry run pytest tests/integration_tests/ -v
   ```

### Phase 3: 不要なマーカー削除（10分）

6. **`@pytest.mark.no_db_setup` マーカーを検索して削除**
   ```bash
   # 検索
   grep -r "no_db_setup" tests/
   ```

7. **conftest.py からマーカーチェックを削除**
   ```python
   # 削除
   if request.node.get_closest_marker('no_db_setup'):
       yield
       return
   ```

**総見積もり**: 55分

---

## テスト計画

### 1. Unit テスト

```bash
poetry run pytest tests/unit_tests/ -v
```

**期待結果**:
- 全テストがパス
- DB不要なテストは高速化（setup不実行）

### 2. Behavior テスト

```bash
poetry run pytest tests/behavior_tests/ -v
```

**期待結果**:
- 全テストがパス

### 3. Integration テスト（PostgreSQL）

```bash
poetry run pytest tests/integration_tests/ -v
```

**期待結果**:
- 全テストがパス

### 4. パフォーマンス確認

```bash
# 修正前のテスト実行時間を記録
poetry run pytest tests/unit_tests/ --durations=0

# 修正後の時間と比較
```

**期待**:
- DB不要なテストが高速化

---

## 完了基準

- ✅ `setup_repom_db_tables` から `autouse=True` が削除されている
- ✅ `setup_postgres_tables` から `autouse=True` が削除されている
- ✅ DB接続が必要なテストに明示的に fixture が追加されている
- ✅ `@pytest.mark.no_db_setup` マーカーとそのチェックが削除されている
- ✅ 全テスト（Unit/Behavior/Integration）がパスする
- ✅ テスト実行時間が改善されている（DB不要なテスト）

---

## メリット

### 1. **パフォーマンス向上**
- DB不要なテストでengine作成をスキップ
- テスト実行時間が短縮

### 2. **明確な意図**
- テストコードを見ればDB接続の有無が分かる
- デバッグが容易

### 3. **柔軟性向上**
- テストごとに制御可能
- 新しいテストを追加しやすい

### 4. **正しい設計**
- 「必要なテストで使う」が正しい
- 「不要なテストで除外する」ではない

---

## 関連Issue

- **親Issue**: [Issue #028: テストアーキテクチャの複雑性](028_test_architecture_complexity.md)
- **関連**: Issue #035 (SQLite/PostgreSQL fixture分離) - 独立して実装可能
- **関連**: Issue #036 (fixture scope見直し) - 独立して実装可能

---

## 備考

### なぜ優先度が高いか

1. **低リスク**: fixture内容は変更しない、指定方法のみ変更
2. **高効果**: パフォーマンス改善、可読性向上
3. **独立性**: 他のIssueと独立して実装可能
4. **基礎**: 他のIssue（#035, #036）の前提となる改善

### 実装の注意点

- 既存のテストを壊さないよう、段階的に進める
- `db_test` fixtureを使うテストは影響を受けない可能性が高い
- 失敗したテストから順次修正すればOK

---

**最終更新**: 2026-02-04
