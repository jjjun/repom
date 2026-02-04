# Issue #033: config 直接設定の削除（バグ修正）

**ステータス**: 🔴 未着手

**作成日**: 2026-02-04

**優先度**: 高

**複雑度**: 低

---

## 問題の説明

テストコード内で `config.exec_env = "dev"` のような直接設定が行われているが、**これは効果がなく、バグの温床になっている**。

### 現状の問題コード

```python
# tests/unit_tests/test_multithread_memory_db.py (line 58)
config = RepomConfig()
config.exec_env = "test"  # ← これは効果がない！
```

### なぜ効果がないか

`RepomConfig` は dataclass であり、`exec_env` は初期化時に環境変数から読み込まれる：

```python
# repom/_/config_hook.py (line 66)
@dataclass
class Config:
    # 実行環境(dev/test/prod)
    exec_env: str = field(default=os.getenv('EXEC_ENV', 'dev'))
```

**問題の流れ**:

1. `config = RepomConfig()` の時点で `os.environ['EXEC_ENV']` の値が `exec_env` に読み込まれる
2. その後 `config.exec_env = "test"` と設定しても、**dataclass のフィールドに代入されるだけ**
3. `db_url`、`postgres_db` などの `@property` は内部で `self.exec_env` を参照する
4. しかし、**プロパティの計算結果はキャッシュされていない**ため、実際には環境変数から計算され続ける
5. 結果的に `config.exec_env = "test"` は **無意味**

### 実際の影響

現在のコードでは、`os.environ["EXEC_ENV"] = "test"` を先に設定しているため、**結果的には動作している**。

しかし、`config.exec_env = "test"` の行は：
- **完全に無意味**
- **誤解を招く**（この行が効果があると勘違いする）
- **バグの温床**（将来的に環境変数設定を忘れてもエラーにならない）

---

## 期待される動作

config の設定は **環境変数のみ**、または **CONFIG_HOOK** 経由で行うべき。

### 正しいパターン

```python
# ✅ 正しい方法1: 環境変数で設定
os.environ["EXEC_ENV"] = "test"
config = RepomConfig()  # 環境変数を読み込んでインスタンス化

# ✅ 正しい方法2: CONFIG_HOOK で設定（外部プロジェクト）
# CONFIG_HOOK=mine_py.config:get_repom_config
def get_repom_config():
    config = RepomConfig()
    # ここで設定をカスタマイズ
    return config
```

### 間違ったパターン

```python
# ❌ 間違い: インスタンス化後に直接設定
config = RepomConfig()
config.exec_env = "test"  # 効果なし
config.db_type = "postgres"  # これも効果なし（環境変数が優先される場合）
```

---

## 提案される解決策

### 1. 無意味な直接設定を削除

すべての `config.exec_env = "..."` のような行を削除する。

### 2. 該当箇所のリスト

調査結果から、以下の箇所で直接設定が行われている：

| ファイル | 行 | コード | 対応 |
|---------|---|--------|------|
| `tests/unit_tests/test_multithread_memory_db.py` | 58 | `config.exec_env = "test"` | 削除 |
| `tests/unit_tests/test_multithread_memory_db.py` | 251 | `config.exec_env = "test"` | 削除 |
| `tests/unit_tests/test_multithread_memory_db.py` | 276 | `config.exec_env = "dev"` | 削除 |

**注意**: 環境変数 `os.environ["EXEC_ENV"]` の設定は**残す**（これは正しい方法）。

---

## 影響範囲

### 変更が必要なファイル

1. **tests/unit_tests/test_multithread_memory_db.py**
   - 3箇所の `config.exec_env = "..."` を削除

### 影響を受けるテスト

- `tests/unit_tests/test_multithread_memory_db.py` の全テスト
  - **期待**: 全テストがパスし続ける（環境変数で正しく設定されているため）

### リスク

- **極めて低リスク**: 無意味な行を削除するだけ
- **副作用なし**: 環境変数の設定は残すため、動作は変わらない

---

## 実装計画

### Phase 1: コード修正（5分）

1. **tests/unit_tests/test_multithread_memory_db.py を修正**
   - 3箇所の `config.exec_env = "..."` を削除
   - コメントも適切に更新

### Phase 2: テストとバリデーション（5分）

2. **該当テストを実行**
   ```bash
   poetry run pytest tests/unit_tests/test_multithread_memory_db.py -v
   ```
   - 期待: 全テストがパス

3. **全テストを実行**
   ```bash
   poetry run pytest tests/unit_tests/
   ```
   - 期待: 既存テストが壊れていないことを確認

**総見積もり**: 10分

---

## 実装の詳細

### 変更例

#### tests/unit_tests/test_multithread_memory_db.py

**変更前**:
```python
try:
    config = RepomConfig()
    config.exec_env = "test"  # 明示的に test 環境に設定
    # use_in_memory_db_for_tests が True であることを確認
    assert config.sqlite.use_in_memory_for_tests is True
```

**変更後**:
```python
try:
    config = RepomConfig()
    # 環境変数 EXEC_ENV='test' が設定済みのため、自動的に test 環境になる
    # use_in_memory_db_for_tests が True であることを確認
    assert config.sqlite.use_in_memory_for_tests is True
```

**理由**:
- `os.environ["EXEC_ENV"] = "test"` は既に設定されている（上の行で）
- `config = RepomConfig()` でインスタンス化時に自動的に読み込まれる
- 追加の設定は不要

---

## テスト計画

### 1. 該当テストの実行

```bash
# test_multithread_memory_db.py のテスト
poetry run pytest tests/unit_tests/test_multithread_memory_db.py -v
```

**期待結果**:
- 全テストがパス
- 動作に変化なし（環境変数が正しく適用されている）

### 2. 全 Unit テストの回帰テスト

```bash
poetry run pytest tests/unit_tests/ -v
```

**期待結果**:
- 既存テストが壊れていない
- 全テストがパス

---

## 完了基準

- ✅ `tests/unit_tests/test_multithread_memory_db.py` から3箇所の `config.exec_env = "..."` が削除されている
- ✅ コメントが適切に更新されている
- ✅ 該当テストファイルの全テストがパスする
- ✅ 全 Unit テストがパスする（回帰なし）
- ✅ コードレビュー：他に同様の直接設定がないことを確認

---

## 関連 Issue

- **Issue #028**: テストアーキテクチャの複雑性（親Issue）
- **Issue #032**: PostgreSQL 統合テストの EXEC_ENV 修正（並行作業）

---

## 備考

### なぜこの修正が必要か

1. **バグの温床を排除**
   - 無意味なコードは混乱を招く
   - 将来的なバグを防ぐ

2. **コードの意図を明確にする**
   - 環境変数のみで設定することを明示
   - CONFIG_HOOK の存在意義が明確になる

3. **メンテナンス性の向上**
   - 誤解を招くコードを削除
   - 新しい開発者が理解しやすくなる

### CONFIG_HOOK の役割

CONFIG_HOOK は **外部プロジェクト**（例: mine-py）が repom の設定をカスタマイズするための仕組み：

```python
# mine-py/src/mine_py/config.py
def get_repom_config():
    config = RepomConfig()
    config.postgres.database = 'mine_py'  # カスタマイズ
    config.model_locations = ['mine_py.models']
    return config
```

**重要**: CONFIG_HOOK はインスタンス化時に適用されるため、後から直接設定しても意味がない。

### 優先度が高い理由

- **バグ**: 無意味な設定がコード内に存在している
- **誤解を招く**: 効果があるように見えて実際は効果がない
- **シンプルな修正**: 行を削除するだけ
- **低リスク**: 環境変数の設定は残すため、動作は変わらない

---

## 追加の推奨事項

### 将来的な改善（別Issue）

1. **config の不変性を強化**
   - dataclass(frozen=True) を検討
   - 直接設定を防ぐ

2. **ドキュメントの強化**
   - CONFIG_HOOK の使い方を明確に記載
   - 環境変数による設定方法を強調

3. **Linter ルールの追加**
   - `config.exec_env =` のようなパターンを警告

---

**最終更新**: 2026-02-04
