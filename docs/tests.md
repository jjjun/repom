# repom テストガイド

`repom`パッケージに含まれる共通コンポーネントの品質を担保するためのテスト情報をまとめています。

## テストの実行

### 基本的な実行方法
```bash
# プロジェクトルートで実行
poetry install  # 初回のみ
poetry run pytest

# すべてのテストを詳細表示で実行
poetry run pytest -v

# 特定のカテゴリのみ実行
poetry run pytest tests/unit_tests
poetry run pytest tests/behavior_tests

# 特定のファイルのみ実行
poetry run pytest tests/unit_tests/test_config.py
```

### VS Code以外の環境（GitHub Copilot CLI、OpenAI Codexなど）
VS Codeを使わない環境でも、上記のコマンドをそのまま使用できます：

```bash
# ターミナルから直接実行
cd /path/to/repom
poetry run pytest tests/unit_tests -v
```

## ディレクトリ構造

```
tests/
├── conftest.py          # 全テスト向けの環境変数設定
├── db_test_fixtures.py  # DB セッションフィクスチャ
├── behavior_tests/      # 共有機能の振る舞いテスト
├── unit_tests/          # フック・ユーティリティ単体テスト
└── utils.py             # テスト補助関数
```

## 主なフィクスチャとサポートコード

### `pytest_configure` (`tests/conftest.py`)
- `EXEC_ENV=test`を設定し、テスト用 SQLite データベース（`data/repom/db.test.sqlite3`）を利用させます
- `CONFIG_HOOK` を空文字列にすることで、親プロジェクト（py-mine）の設定フックを無効化し、repom を単体でテストできるようにしています

### `db_test` フィクスチャ (`tests/db_test_fixtures.py`)
- テストごとにクリーンなデータベース環境を提供します
- 各テスト関数の実行前に`db_create()`でデータベースを作成
- テスト実行後に`db_delete()`でデータベースを削除
- SQLAlchemyの`db_session`をyieldします

**スコープ**: `function`（デフォルト）
- 各テスト関数ごとに独立したデータベースを作成・削除
- テスト間での状態の持ち越しがなく、テストの独立性を保証

## テストが利用する主な環境変数

### `EXEC_ENV`
- テスト専用のデータベース設定を選択するため `test` に固定
- `conftest.py`の`pytest_configure`で自動設定されます
- 結果：`data/repom/db.test.sqlite3`が使用されます

### `CONFIG_HOOK`
- 親プロジェクトの設定フックを制御
- テスト時は空文字列に設定され、repom単体での動作を保証
- 通常の開発時は`.env`で`CONFIG_HOOK=mine_py:hook_config`のように設定可能

## 実行時の注意事項

### データベースの扱い
- **並列実行は非推奨**: データベースを操作するテストが多いため、複数プロセス並列（`-n`オプション）は推奨されません
- **データベースの場所**: テストデータベースは`data/repom/db.test.sqlite3`に作成されます
- **クリーンアップ**: `db_test`フィクスチャが自動的にデータベースを削除しますが、テスト失敗時に残る場合があります
  ```bash
  # 手動でクリーンアップする場合
  poetry run db_delete
  # または直接削除
  Remove-Item data/repom/db.test.sqlite3  # Windows PowerShell
  rm data/repom/db.test.sqlite3            # Unix系
  ```

### テストの独立性
- 各テスト関数は独立したデータベースで実行されます
- テスト間でデータが共有されることはありません
- テストの実行順序に依存しない設計になっています

## 設定クラス (`MineDbConfig`) の検証

### テストファイル
**`tests/unit_tests/test_config.py`**

### 検証内容
- ✅ **`db_path`**: 既定で`data_path`を参照し、任意に上書きできることを確認
- ✅ **`db_file`**: `exec_env`に応じて以下のファイル名になることを検証
  - `test` → `db.test.sqlite3`
  - `dev` → `db.dev.sqlite3`
  - `prod` → `db.sqlite3`
- ✅ **`db_file_path`**: `db_path`と`db_file`を結合したフルパスが正しく構築されることを確認
- ✅ **`db_url`**: 既定で`sqlite:///{db_path}/{db_file}`形式になり、任意のURLを設定できることを検証
- ✅ **`db_backup_path`**: 既定で`data_path/backups`配下になり、別ディレクトリに変更できることを確認

### テスト対象外
- `alembic_path` / `alembic_versions_path`はAlembic設定ファイル（`alembic.ini`）への依存が大きいため、単体テストでは検証していません

## テストカバレッジ

### Unit Tests (`tests/unit_tests/`)
- **`test_config.py`**: 設定クラスの動作検証（12テスト）
- **`test_model.py`**: BaseModelの機能検証（5テスト）
- **`test_repository.py`**: BaseRepositoryのCRUD操作検証（17テスト）
- **`custom_types/`**: カスタム型の動作検証
  - `test_createdat.py`: CreatedAt型（2テスト）
  - `test_jsonencoded.py`: JSONEncoded型（5テスト）
  - `test_listjson.py`: ListJSON型（5テスト）

### Behavior Tests (`tests/behavior_tests/`)
- **`test_unique_key_handling.py`**: ユニークキー制約の振る舞い
- **`test_date_type_comparison.py`**: 日付型の比較とSQLite型の挙動

**合計**: 42テスト（執筆時点）

## CI/CD環境での実行

GitHub Actions、GitLab CI、その他のCI環境でも同じコマンドが使用できます：

```yaml
# GitHub Actions の例
- name: Run tests
  run: |
    poetry install
    poetry run pytest tests/unit_tests -v
```

## トラブルシューティング

### テストが失敗する場合
1. 環境変数を確認: `EXEC_ENV=test`が設定されているか
2. データベースをクリーンアップ: `poetry run db_delete`
3. 依存関係を再インストール: `poetry install --sync`

### モジュールが見つからないエラー
- `poetry install`を実行して依存関係をインストール
- 仮想環境が有効になっているか確認: `poetry env info`
