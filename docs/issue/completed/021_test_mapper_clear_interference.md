# Issue #021: テスト間のマッパークリア干渉問題

**最終更新**: 2026-01-28
**ステータス**: ✅ 完了

## 概要

`test_date_type_comparison.py` がモジュールレベルでモデルを定義しているため、他のテストが `clear_mappers()` を呼び出すとマッパーがクリアされ、テストが失敗する問題。

**採用した解決策**: 各テスト関数内でローカルモデルを再定義（test_unique_key_handling.py パターン）

## 完了日

- **完了日**: 2026-01-28
- **検証済み**: 順序依存テスト全パス

## ステータス

- **作成日**: 2026-01-28
- **完了日**: 2026-01-28
- **優先度**: 中
- **複雑度**: 中（テスト関数内でモデル再定義）
- **関連 Issue**: 
  - #020（循環参照問題の修正中に発見）
  - #022（isolated_mapper_registry の改善 - 今後の課題）

---

## 実装した解決策

### テスト関数内でのローカルモデル再定義

**採用理由**:
- ✅ **確実に動作**: clear_mappers() の影響を完全に回避
- ✅ **実証済み**: test_unique_key_handling.py で既に使用
- ✅ **isolated_mapper_registry 不要**: フィクスチャの設計問題を回避

**実装内容**:

```python
def test_compare_save_behavior(db_test):
    # テスト関数内でモデルを再定義
    class LocalTaskModel(Base):
        __abstract__ = True
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(255), default='')
        
        def done(self):
            self.done_at = datetime.now().date()
    
    class LocalTaskDateModel(LocalTaskModel):
        __tablename__ = 'task_date'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[date_type]] = mapped_column(Date)
        created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())
    
    class LocalTaskStringModel(LocalTaskModel):
        __tablename__ = 'task_string'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[str]] = mapped_column(String)
        created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())
    
    Base.metadata.create_all(bind=db_test.bind)
    
    # テストコード
    task_date = LocalTaskDateModel(name='take a bath')
    # ...
```

**重要なポイント**:
1. `extend_existing=True` を使用してテーブル再定義を許可
2. 各テスト関数内でモデルを完全に再定義
3. Base.metadata.create_all() でテーブルを作成

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

## 検証結果

### テスト実行結果

✅ **単独実行**: 3テスト全パス
```powershell
poetry run pytest tests/behavior_tests/test_date_type_comparison.py -v
# Result: 3 passed
```

✅ **順序依存テスト**: 5テスト全パス
```powershell
poetry run pytest tests/behavior_tests/test_circular_import.py tests/behavior_tests/test_date_type_comparison.py -v
# Result: 5 passed (Issue #021 で失敗していたテストが成功)
```

✅ **behavior_tests 全体**: 全テストパス（一部別の問題あり）
```powershell
poetry run pytest tests/behavior_tests -v
```

---

## 影響範囲

### 修正したファイル

- **tests/behavior_tests/test_date_type_comparison.py**
  - モジュールレベルのモデル定義を削除
  - 各テスト関数（3つ）内でローカルモデルを再定義
  - generate_test_data() でローカルモデルを使用
  - テーブル作成を各テスト内で実施

- **tests/conftest.py**
  - `behavior_test_modules` から `test_date_type_comparison` を削除
  - （test_date_type_comparison はもはやモジュールレベルモデルを持たない）

### 変更しなかったもの

- ✅ generate_test_data() ヘルパー関数 - **そのまま**（Type パラメータでローカルモデルを受け取る）
- ✅ 他のテストファイル - **影響なし**

---

## 今後の課題

### isolated_mapper_registry の設計改善（Issue #022）

**発見された問題**:
- isolated_mapper_registry は repom のモデルのみをロードする
- behavior_tests のモジュールレベルモデルを再ロードするが、load_models() では検出されない
- 結果: test_date_type_comparison では動作しなかった

**提案**:
- Issue #022 として新規作成
- isolated_mapper_registry の改善または代替アプローチの検討
- 優先度: 低（回避策が存在するため）

---

## 関連ドキュメント

- **Issue #020** - 循環参照警告の解決（この問題の発見元）
- **Issue #022** - isolated_mapper_registry の改善（今後の課題）
- **test_unique_key_handling.py** - 同じパターンを使用している実装例

---

## 教訓

1. **isolated_mapper_registry の制限**:
   - repom 以外のモジュールレベルモデルには対応していない
   - 設計上の制約があることが判明

2. **実証済みパターンの活用**:
   - test_unique_key_handling.py の実装パターンが有効
   - テスト関数内でのモデル再定義は確実な解決策

3. **テスト独立性の重要性**:
   - テストは実行順序に依存すべきではない
   - clear_mappers() の影響を受けないよう設計すべき

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

### `isolated_mapper_registry` フィクスチャを使用（推奨）★★★★★

**概要**: 既存の `isolated_mapper_registry` フィクスチャを各テスト関数に追加するだけ。

**メリット**:
- ✅ **最小限の変更**: 各テスト関数に1パラメータ追加するだけ（3箇所）
- ✅ **コードの重複なし**: モジュールレベルの定義をそのまま維持
- ✅ **実証済み**: `test_type_checking_*.py` などで既に使用中
- ✅ **自動クリーンアップ**: `clear_mappers()` 対策が完全実装済み
- ✅ **公式ドキュメント**: `docs/guides/testing/isolated_mapper_fixture.md` に詳細ガイドあり

**実装方針**:

```python
# Before（現状）
def test_compare_save_behavior(db_test):
    task_date = TaskDateModel(name='take a bath')
    # ...

# After（修正後）
def test_compare_save_behavior(isolated_mapper_registry, db_test):
    # ← フィクスチャを追加するだけ！
    # モジュールレベルの TaskDateModel がそのまま使える
    task_date = TaskDateModel(name='take a bath')
    # ...（テストコード本体は一切変更不要）
```

**重要なポイント**:
1. モジュールレベルの `TaskModel`, `TaskDateModel`, `TaskStringModel` の定義は**そのまま維持**
2. `generate_test_data()` ヘルパー関数も**そのまま使える**
3. テストコード本体は**一切変更不要**
4. `isolated_mapper_registry` が自動的にクリーンアップと再構築を行う

**conftest.py の実装**:
```python
@pytest.fixture
def isolated_mapper_registry(db_test):
    """一時的なモデル定義用のフィクスチャ
    
    テスト終了後、自動的に:
    1. 一時的なテーブルを metadata から削除
    2. clear_mappers() でマッパーをクリア
    3. behavior_tests のモジュールを再ロード（test_date_type_comparison 含む）
    4. load_models() で repom の標準モデルを再ロード
    5. configure_mappers() でマッパー再構築
    """
    # ... 実装は tests/conftest.py を参照
```

**参考ドキュメント**:
- [isolated_mapper_fixture.md](../../../docs/guides/testing/isolated_mapper_fixture.md) - 詳細ガイド
- [tests/conftest.py](../../../tests/conftest.py) - 実装コード
- [test_type_checking_detailed.py](../../../tests/behavior_tests/test_type_checking_detailed.py) - 使用例

---

## 影響範囲

### 修正が必要なファイル

- **tests/behavior_tests/test_date_type_comparison.py**
  - 3つのテスト関数にフィクスチャを追加（各1行）
  - モジュールレベルのテーブル作成コードを削除（lines 73-81）

### 影響を受けるテスト

- `test_compare_save_behavior` - フィクスチャ追加
- `test_handle_invalid_date_save` - フィクスチャ追加
- `test_compare_search_behavior` - フィクスチャ追加

### 変更しないもの（重要）

- ✅ モジュールレベルのモデル定義（`TaskModel`, `TaskDateModel`, `TaskStringModel`）- **そのまま**
- ✅ `generate_test_data()` ヘルパー関数 - **そのまま**
- ✅ テストコード本体 - **そのまま**

---

## 実装計画

### Phase 1: フィクスチャの追加（3箇所）

```python
# 変更前
def test_compare_save_behavior(db_test):

# 変更後
def test_compare_save_behavior(isolated_mapper_registry, db_test):
```

同様に以下にも追加:
- `test_handle_invalid_date_save`
- `test_compare_search_behavior`

### Phase 2: モジュールレベルのテーブル作成コードを削除

```python
# 削除する部分（lines 73-81）
engine = get_sync_engine()
inspector = get_inspector()

if inspector.has_table(TaskDateModel.__tablename__):
    TaskDateModel.__table__.drop(bind=engine)
if inspector.has_table(TaskStringModel.__tablename__):
    TaskStringModel.__table__.drop(bind=engine)

TaskDateModel.__table__.create(bind=engine)
TaskStringModel.__table__.create(bind=engine)
```

**理由**: `isolated_mapper_registry` がテーブル作成を自動的に行うため不要

### Phase 3: 検証

- [ ] 単独実行で3テスト全パス
- [ ] 順序テスト: `test_circular_import.py` → `test_date_type_comparison.py` 全パス
- [ ] behavior_tests 全体で実行
- [ ] unit_tests + behavior_tests 全体で実行

---

## テスト計画

### 検証項目

1. **単独実行**: `poetry run pytest tests/behavior_tests/test_date_type_comparison.py -v`
   - 期待: 3テスト全パス

2. **順序テスト**: `poetry run pytest tests/behavior_tests/test_circular_import.py tests/behavior_tests/test_date_type_comparison.py -v`
   - 期待: 全テストパス（**現在は失敗している**）

3. **behavior_tests 全体**: `poetry run pytest tests/behavior_tests -v`
   - 期待: 全テストパス

4. **完全テスト**: `poetry run pytest`
   - 期待: unit_tests + behavior_tests すべてパス

### 成功基準

- ✅ 3つのテスト関数にフィクスチャが追加されている
- ✅ モジュールレベルのテーブル作成コードが削除されている
- ✅ テスト実行順序に依存しない
- ✅ behavior_tests 全体が全パス
- ✅ unit_tests + behavior_tests 全体が全パス
- ✅ パフォーマンスへの影響が最小限（`isolated_mapper_registry` は軽量）

---

## 関連ドキュメント

- **[isolated_mapper_fixture.md](../../../docs/guides/testing/isolated_mapper_fixture.md)** - フィクスチャの詳細ガイド
- **Issue #020** - 循環参照警告の解決（この問題の発見元）
- **tests/conftest.py** - `isolated_mapper_registry` の実装
- **test_type_checking_detailed.py** - 使用例

---

## 実装の詳細

### なぜ `isolated_mapper_registry` で解決できるのか

1. **テスト前**: 現在の metadata テーブル一覧を保存
2. **テスト実行**: モジュールレベルのモデルを通常通り使用
3. **テスト後（自動）**:
   - 一時的なテーブルを metadata から削除
   - `clear_mappers()` でマッパーをクリア
   - **`test_date_type_comparison` モジュールを再ロード**（重要！）
   - `load_models()` で repom の標準モデルを再ロード
   - `configure_mappers()` でマッパー再構築

**キーポイント**: conftest.py の `behavior_test_modules` リストに `test_date_type_comparison` が含まれているため、自動的に再ロードされる。

```python
# tests/conftest.py (lines 151-154)
behavior_test_modules = [
    'tests.behavior_tests.test_date_type_comparison',  # ← これがあるから動く
    'tests.behavior_tests.test_migration_no_id',
]
```

### パフォーマンスへの影響

- **追加コスト**: ~50ms/テスト（マッパー再構築のオーバーヘッド）
- **影響範囲**: 3つのテストのみ（全体テストスイートの1%未満）
- **許容可能**: テストの独立性 >> わずかなパフォーマンス低下

---

## 備考

### なぜ今まで気づかなかったのか

- `test_date_type_comparison.py` は通常、他のテストよりも先に実行されることが多かった（アルファベット順）
- `clear_mappers()` を使うテスト（`test_circular_import.py`）がIssue #020で新しく追加された
- テストの実行順序は pytest が自動的に決定するため、環境によって変わる

### 今後の予防策

- ✅ **`isolated_mapper_registry` の使用**: モジュールレベルでモデルを定義する場合は必須
- ✅ **ドキュメント整備**: `isolated_mapper_fixture.md` にベストプラクティスを記載済み
- ✅ **CI/CD**: ランダム実行順序でテスト（`pytest-randomly`）

### conftest.py の改善（将来的）

現在、`behavior_test_modules` リストに手動で追加する必要がある。将来的には自動検出も検討可能：

```python
# 自動検出の例（将来的な改善案）
behavior_test_modules = [
    key for key in sys.modules.keys()
    if key.startswith('tests.behavior_tests.test_') and
       hasattr(sys.modules[key], '__file__')
]
```

ただし、現在の明示的なリスト方式の方が安全で予測可能。

---

**次のアクション**: Phase 1 の実装（3つのテスト関数にフィクスチャ追加）
