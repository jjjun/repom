# Issue #021: テスト間のマッパークリア干渉問題

**最終更新**: 2026-01-28
**ステータス**: 🔴 未着手

## 概要

`test_date_type_comparison.py` がモジュールレベルでモデルを定義しているため、他のテストが `clear_mappers()` を呼び出すとマッパーがクリアされ、テストが失敗する問題。

## ステータス

- **作成日**: 2026-01-28
- **優先度**: 中
- **複雑度**: 中
- **関連 Issue**: #020（循環参照問題の修正中に発見）

---

## 問題の説明

### 発生条件

1. `test_circular_import.py` が先に実行される
2. その `clean_circular_import_env` フィクスチャが `clear_mappers()` を呼ぶ
3. `test_date_type_comparison.py` が実行される
4. モジュールレベルで定義された `TaskDateModel`, `TaskStringModel` のマッパーがクリアされている
5. テストが `UnmappedInstanceError` で失敗

### エラーメッセージ

```
sqlalchemy.orm.exc.UnmappedInstanceError: Class 'test_date_type_comparison.TaskDateModel' is not mapped
```

### ログから見える問題

```
DEBUG - Loaded 0 models:
```

→ モデルが0個ロードされている（マッパーがクリアされた証拠）

### 再現方法

```powershell
# 失敗する（test_circular_import.py が先に実行される）
poetry run pytest tests/behavior_tests/test_circular_import.py tests/behavior_tests/test_date_type_comparison.py -v

# 成功する（単独実行）
poetry run pytest tests/behavior_tests/test_date_type_comparison.py -v
```

---

## 期待される動作

- すべてのテストが**実行順序に依存せず**に独立して動作すること
- テストの独立性が保証されること
- 他のテストが `clear_mappers()` を呼んでも影響を受けないこと

---

## 根本原因

### 問題のあるコード

```python
# tests/behavior_tests/test_date_type_comparison.py
# モジュールレベルでモデルを定義
class TaskDateModel(TaskModel):
    __tablename__ = 'task_date'
    done_at: Mapped[Optional[date_type]] = mapped_column(Date)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())

class TaskStringModel(TaskModel):
    __tablename__ = 'task_string'
    done_at: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())

# モジュールレベルでテーブルを作成
engine = get_sync_engine()
TaskDateModel.__table__.create(bind=engine)
TaskStringModel.__table__.create(bind=engine)
```

### なぜ問題なのか

1. **モジュールレベルでモデル定義**: ファイルがインポートされた時点でマッパーが登録される
2. **他のテストが `clear_mappers()` を呼ぶ**: 循環参照テストなど、マッパーをクリアする必要があるテストが存在
3. **マッパーがクリアされる**: `test_date_type_comparison.py` のモデルも影響を受ける
4. **テストが失敗**: `db_test.add()` 時に `UnmappedInstanceError` が発生

---

## 提案される解決策

### Option 1: テスト関数内でモデルを定義（推奨）

**メリット**:
- ✅ テストの独立性が保証される
- ✅ 他のテストの `clear_mappers()` の影響を受けない
- ✅ テストのベストプラクティスに準拠
- ✅ 将来的な問題を防げる

**実装**:

```python
# tests/behavior_tests/test_date_type_comparison.py
def test_compare_save_behavior(db_test):
    """日付型の挙動を確認"""
    
    # テスト関数内でモデルを定義
    class TaskDateModel(TaskModel):
        __tablename__ = 'task_date_test'
        done_at: Mapped[Optional[date_type]] = mapped_column(Date)
        created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())
    
    class TaskStringModel(TaskModel):
        __tablename__ = 'task_string_test'
        done_at: Mapped[Optional[str]] = mapped_column(String)
        created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())
    
    # テーブルを作成
    Base.metadata.create_all(bind=db_test.get_bind())
    
    # テストコード
    task_date = TaskDateModel(name='take a bath')
    task_string = TaskStringModel(name='take a bath')
    # ... 以下同じ
```

### Option 2: pytest fixture でモデルを提供（代替案）

```python
@pytest.fixture
def date_comparison_models(db_test):
    """日付比較用モデルを提供"""
    
    class TaskDateModel(TaskModel):
        __tablename__ = 'task_date_fixture'
        done_at: Mapped[Optional[date_type]] = mapped_column(Date)
        created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())
    
    class TaskStringModel(TaskModel):
        __tablename__ = 'task_string_fixture'
        done_at: Mapped[Optional[str]] = mapped_column(String)
        created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())
    
    Base.metadata.create_all(bind=db_test.get_bind())
    
    return TaskDateModel, TaskStringModel

def test_compare_save_behavior(db_test, date_comparison_models):
    TaskDateModel, TaskStringModel = date_comparison_models
    # テストコード
```

---

## 影響範囲

### 修正が必要なファイル

- **tests/behavior_tests/test_date_type_comparison.py**
  - 3つのテスト関数すべて
  - モジュールレベルのモデル定義を削除
  - テスト関数内またはフィクスチャでモデルを定義

### 影響を受けるテスト

- `test_compare_save_behavior`
- `test_handle_invalid_date_save`
- `test_compare_search_behavior`

---

## 実装計画

### Phase 1: モジュールレベルコードの整理

- [ ] モジュールレベルのモデル定義を削除
- [ ] モジュールレベルのテーブル作成コードを削除

### Phase 2: テスト関数の修正

- [ ] `test_compare_save_behavior` をリファクタリング
- [ ] `test_handle_invalid_date_save` をリファクタリング
- [ ] `test_compare_search_behavior` をリファクタリング

### Phase 3: 検証

- [ ] 単独実行で3テスト全パス
- [ ] behavior_tests 全体で実行して干渉がないことを確認
- [ ] unit_tests + behavior_tests 全体で実行

---

## テスト計画

### 検証項目

1. **単独実行**: `poetry run pytest tests/behavior_tests/test_date_type_comparison.py -v`
   - 期待: 3テスト全パス

2. **順序テスト**: `poetry run pytest tests/behavior_tests/test_circular_import.py tests/behavior_tests/test_date_type_comparison.py -v`
   - 期待: 全テストパス（現在は失敗）

3. **全体実行**: `poetry run pytest tests/behavior_tests -v`
   - 期待: 全テストパス

4. **完全テスト**: `poetry run pytest tests/unit_tests tests/behavior_tests`
   - 期待: 全テストパス

### 成功基準

- ✅ 3つのテスト関数すべてが修正されている
- ✅ テスト実行順序に依存しない
- ✅ behavior_tests 全体（29テスト）が全パス
- ✅ unit_tests + behavior_tests 全体が全パス
- ✅ 実行時間が大幅に増加していない

---

## 関連ドキュメント

- **Issue #020**: 循環参照警告の解決（この問題の発見元）
- **tests/behavior_tests/test_circular_import.py**: `clear_mappers()` を使用するテスト
- **docs/guides/testing/testing_guide.md**: テストのベストプラクティス

---

## 備考

### なぜ今まで気づかなかったのか

- `test_date_type_comparison.py` は通常、他のテストよりも先に実行されることが多かった
- `clear_mappers()` を使うテスト（`test_circular_import.py`）が新しく追加された
- テストの実行順序は pytest が自動的に決定するため、環境によって変わる可能性がある

### 今後の予防策

- **テストのベストプラクティス**: モジュールレベルでのモデル定義を避ける
- **pytest プラグイン**: `pytest-randomly` などでランダム実行順序をテスト
- **CI/CD**: 複数回実行して順序依存をチェック

### 他に影響を受ける可能性があるテスト

現在のところ、`test_date_type_comparison.py` のみが該当する。
他のテストは適切にフィクスチャを使用しているか、モジュールレベルでのモデル定義を避けている。

---

**次のアクション**: Phase 1 の実装（モジュールレベルコードの整理）
