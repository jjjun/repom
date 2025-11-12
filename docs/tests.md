# mine_db テストガイド

`mine_db` サブモジュールに含まれる共通コンポーネントの品質を担保するためのテスト情報をまとめています。

## テストの実行

- ルートで Poetry シェルを利用する場合:
  ```bash
  cd submod/mine_db
  poetry install  # 未インストールの場合
  poetry run pytest
  ```
- 特定のカテゴリのみ実行する例:
  ```bash
  poetry run pytest tests/unit_tests
  poetry run pytest tests/behavior_tests
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

- **`pytest_configure`** (`tests/conftest.py`)
  - `EXEC_ENV=test`を設定し、テスト用 SQLite データベースを利用させます。また、`CONFIG_HOOK` を空にする事で、mine_db を単体でテスト出来るようにしています。
- **`db_test`** (`tests/db_test_fixtures.py`)
  - `poetry run db_create`/`db_delete` 相当のスクリプトを呼び出し、テストごとにクリーンな `db_session` を提供します。

## テストが利用する主な環境変数

- **`EXEC_ENV`**: テスト専用のデータベース設定を選択するため `test` に固定しています。
- **`MINE_DB_LOAD_MODELS`**: 追加モデルローダーの import 先を切り替えるために利用され、`test_hooks.py` でモジュール名や関数名を指定して動作検証を行います。

## 実行時の注意

- データベースを操作するテストが多いため、複数プロセス並列 (`-n` オプション) は推奨されません。
- `tests/db_test_fixtures.py` の `db_test` はセッションごとにデータベースを作成/削除するため、テスト失敗時は `tests/data` 配下のファイルを確認してクリーンアップしてください。

## 設定クラス (`MineDbConfig`) の検証

- **ファイル**: `tests/unit_tests/test_config.py`
  - `db_path` が既定で `data_path` を参照し、任意に上書きできることを確認します。
  - `db_file` が `exec_env` に応じて `db.<env>.sqlite3` (test/dev) または `db.sqlite3` (prod) となり、値を差し替えられることを検証します。
  - `db_file_path` が `db_path` と `db_file` の組み合わせで構築されることをテストします。
  - `db_url` が既定で `sqlite:///{db_path}/{db_file}` 形式となり、任意の URL を設定できることを確認します。
  - `db_backup_path` が既定で `data_path/backups` 配下になり、別ディレクトリに変更できることを保証します。
- `alembic_path` / `alembic_versions_path` は Alembic 設定ファイルへの依存が大きいため、単体テストでは検証していません。
