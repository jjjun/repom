# Issue #036: Fixture Scope の見直し

**ステータス**: 🟡 提案中（要検討）

**作成日**: 2026-02-04

**優先度**: 低

**複雑度**: 高

**親Issue**: [Issue #028: テストアーキテクチャの複雑性](028_test_architecture_complexity.md)

**前提Issue**: Issue #034, #035 - 先に実装推奨

---

## 問題の説明

現在、`setup_repom_db_tables` などのfixtureは `scope='session'` で定義されている。これにより、**一度初期化したら変更できない**という制約がある。

### 現状のコード

```python
# tests/conftest.py
@pytest.fixture(scope='session', autouse=True)
def setup_repom_db_tables(request):
    """session scope = テストセッション全体で1回だけ実行"""
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    # ...
```

### 問題点

#### 1. **環境を切り替えられない**

```python
# テストA: test環境でテスト
def test_in_test_env():
    # EXEC_ENV='test' で実行
    pass

# テストB: dev環境でテストしたい
# → 無理！session scopeで既に初期化済み
def test_in_dev_env():
    # EXEC_ENV='dev' に変更したい...
    pass
```

**問題**:
- session scope = 1回だけ初期化
- 途中で環境変更できない
- 環境ごとのテストが困難

#### 2. **テストの独立性が低い**

```python
# テストA: データを作成
def test_create_data(db_test):
    user = User(name="test")
    db_test.add(user)
    db_test.commit()

# テストB: 前のテストの影響を受ける可能性
# → db_testはfunction scopeで独立しているが、
#    session scopeのfixtureは共有されている
def test_independent(db_test):
    pass
```

**問題**:
- session scopeのリソースは全テストで共有
- テストの順序依存性が生まれる可能性
- ただし、現在はTransaction Rollbackパターンで緩和されている

#### 3. **柔軟性の欠如**

```python
# 特定のテストでテーブル構造を変更したい
def test_with_custom_schema(db_test):
    # カスタムスキーマでテストしたい...
    # → session scopeで既にテーブル作成済み
    pass
```

---

## 期待される動作

### オプション1: Function Scope（最も独立性が高い）

```python
@pytest.fixture(scope='function')
def setup_db_tables():
    """各テスト関数ごとに実行"""
    # テーブル作成
    yield
    # クリーンアップ
```

**メリット**:
- ✅ テストの完全な独立性
- ✅ 環境切り替え可能
- ✅ カスタムスキーマ対応

**デメリット**:
- ❌ 遅い（毎回テーブル作成）
- ❌ オーバーヘッド大

### オプション2: Class Scope（中間的）

```python
@pytest.fixture(scope='class')
def setup_db_tables():
    """テストクラスごとに実行"""
    pass
```

**メリット**:
- ✅ クラス内でテーブル共有
- ✅ クラス間で独立

**デメリット**:
- ⚠️ クラスベーステストが必要
- ⚠️ 関数ベーステストでは効果なし

### オプション3: Session Scope維持（現状）

```python
@pytest.fixture(scope='session')
def setup_db_tables():
    """現状維持"""
    pass
```

**メリット**:
- ✅ 高速（1回だけ実行）
- ✅ 既存テストへの影響なし

**デメリット**:
- ❌ 柔軟性なし
- ❌ 環境切り替え不可

---

## 調査が必要な項目

### 1. **現在のテスト実行時間**

```bash
# session scopeでの実行時間
poetry run pytest tests/unit_tests/ --durations=0
```

**調査内容**:
- setup_repom_db_tables の実行時間
- function scopeに変更した場合の影響予測

### 2. **Transaction Rollbackパターンとの相性**

現在、repomは**Transaction Rollback**パターンを使用：

```python
# tests/conftest.py
db_engine, db_test = create_test_fixtures()
```

**調査内容**:
- function scopeとTransaction Rollbackの組み合わせ
- パフォーマンス影響
- テーブル作成のオーバーヘッド

### 3. **環境切り替えの必要性**

```bash
# 実際にこのようなテストが必要か？
def test_in_test_env():
    pass

def test_in_dev_env():
    pass
```

**調査内容**:
- 環境切り替えが必要なテストケースの有無
- 現実的な使用シナリオ

### 4. **他プロジェクトでの事例**

**調査内容**:
- SQLAlchemyプロジェクトの一般的なパターン
- pytest-sqlalchemyの推奨パターン
- 他のOSSプロジェクトの事例

---

## 提案される解決策

### 案1: Hybrid Scope（推奨）

```python
# デフォルトはsession scope（高速）
@pytest.fixture(scope='session')
def setup_db_tables_session():
    """高速だが柔軟性なし"""
    pass

# 必要に応じてfunction scope（柔軟）
@pytest.fixture(scope='function')
def setup_db_tables_function():
    """遅いが柔軟性あり"""
    pass

# エイリアス（デフォルトはsession）
@pytest.fixture
def setup_db_tables():
    return setup_db_tables_session()
```

**使用例**:
```python
# 通常のテスト（session scope）
def test_normal(setup_db_tables, db_test):
    pass

# 特殊なテスト（function scope）
def test_special(setup_db_tables_function, db_test):
    pass
```

### 案2: Session Scope維持（最も安全）

現状維持。調査の結果、問題がなければこれを選択。

### 案3: Function Scope全面採用（最もリスク高）

全てfunction scopeに変更。パフォーマンス影響を慎重に評価。

---

## 影響範囲

### 変更が必要なファイル（案1の場合）

1. **tests/conftest.py**
   - `setup_db_tables_session` 作成
   - `setup_db_tables_function` 作成

2. **特殊なテストファイル**
   - function scopeが必要なテストのみ変更

### リスク評価

- **案1**: 低リスク（後方互換性維持）
- **案2**: リスクなし（現状維持）
- **案3**: 高リスク（全テスト影響、パフォーマンス低下の可能性）

---

## 実装計画

### Phase 1: 調査と評価（60分）

1. **現在のテスト実行時間を測定**
   ```bash
   poetry run pytest tests/unit_tests/ --durations=10
   ```

2. **Transaction Rollbackパターンとの相性を評価**
   - ドキュメント調査
   - 簡単なプロトタイプ作成

3. **環境切り替えの必要性を確認**
   - 既存テストの調査
   - 将来的なユースケースの検討

4. **他プロジェクトの事例調査**
   - pytest-sqlalchemy
   - 大規模SQLAlchemyプロジェクト

### Phase 2: 実装判断（30分）

5. **調査結果に基づいて方針決定**
   - 案1: Hybrid Scope
   - 案2: 現状維持
   - 案3: Function Scope全面採用

6. **実装計画の詳細化**
   - 必要に応じてIssueを更新

### Phase 3: 実装（案1の場合、60分）

7. **Hybrid Scope fixtureの作成**
8. **テストと検証**
9. **ドキュメント更新**

**総見積もり**: 150分（調査含む）

---

## 完了基準

### 調査フェーズ
- ✅ テスト実行時間が測定されている
- ✅ Transaction Rollbackパターンとの相性が評価されている
- ✅ 環境切り替えの必要性が確認されている
- ✅ 他プロジェクトの事例が調査されている
- ✅ 実装方針が決定されている

### 実装フェーズ（実装する場合）
- ✅ 選択した案が実装されている
- ✅ 全テストがパスする
- ✅ パフォーマンス劣化がない（または許容範囲）
- ✅ ドキュメントが更新されている

---

## 関連Issue

- **親Issue**: [Issue #028: テストアーキテクチャの複雑性](028_test_architecture_complexity.md)
- **前提**: Issue #034 (autouse=True削除) - 先に実装推奨
- **前提**: Issue #035 (SQLite/PostgreSQL分離) - 先に実装推奨

---

## 備考

### なぜ優先度が低いか

1. **現状で大きな問題がない**
   - Transaction Rollbackパターンで独立性は確保されている
   - 環境切り替えが必要なケースが少ない

2. **高リスク**
   - scope変更は広範囲に影響
   - パフォーマンス低下の可能性

3. **他のIssueが前提**
   - Issue #034, #035を先に実装すべき

### 実装判断の基準

以下の場合のみ実装を推奨：

- ✅ 環境切り替えが必要なテストケースが実際に存在する
- ✅ パフォーマンス影響が許容範囲（+10%以内）
- ✅ Transaction Rollbackパターンと相性が良い
- ✅ Issue #034, #035が完了している

それ以外の場合は**現状維持（案2）**を推奨。

---

**最終更新**: 2026-02-04
