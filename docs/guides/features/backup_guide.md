# repom バックアップ / リストアガイド

`db_backup` と `db_restore` は console script として提供される手動実行用の
コマンドです。PostgreSQL と SQLite の両方に対応し、実体は
`repom/scripts/db_backup.py`、`repom/scripts/db_restore.py`、共有ヘルパーの
`repom/scripts/_backup_utils.py` にあります。

## スケジューリングは利用側の責務

repom 自身はバックアップを定期実行する仕組み（cron、スケジューラ）を一切持ちません。
`db_backup` / `db_restore` はいつでも手動で実行できる console script であり、
定期実行が必要な場合は利用側アプリケーションが用意します（例: fast-domain は
arq worker の daily cron から `db_backup` を実行しています）。

そのため、開発環境の checkout でバックアップディレクトリが空だったり、
最終更新日が古いのは正常な状態です。定期実行を仕込んでいない checkout では、
誰かが手動で実行しない限りバックアップは増えません。故障の兆候ではないので、
バックアップが必要なら明示的に `uv run db_backup` を実行してください。

```bash
uv run db_backup
```

## 配置とファイル名

バックアップは `config.db_backup_path` 配下に作成されます。既定値は
`<data_path>/backups/<db_type>`（db_type ごとに分かれたディレクトリ）ですが、
`db_backup_path` を明示的に上書きした場合はそのパス直下にバックアップファイルが
書き込まれます（`postgres` / `sqlite` サブディレクトリは追加されません）。

- PostgreSQL: `<data_path>/backups/postgres/<postgres_db>_<YYYYmmdd_HHMMSS>.sql.gz`
- SQLite: `<data_path>/backups/sqlite/<db のファイル名 stem>_<YYYYmmdd_HHMMSS><db のファイル名拡張子>`

従来の `.sqlite3` バックアップも引き続き一覧に表示されます。

いずれも作成のたびに `.sha256` サイドカーファイル（`write_checksum()`）が
書き込まれ、`db_restore` はリストア前にこれを検証します
（`warn_if_checksum_missing()`）。サイドカーが存在しない古いバックアップは
警告を出すだけでリストアは継続し、サイドカーはあるが値が一致しない場合は
`ChecksumError` が `RestoreError` に wrap されて呼び出し元へ通知され、リストアを
中断します。

## データベース接続先

`config.db_url` が上書きされている場合、`db_backup` / `db_restore` はその URL を接続先に
します。PostgreSQL ではクライアント引数、パスワード、TLS 設定を URL から取得し、管理対象
コンテナの状態確認や `docker exec` を行わず、host 上で `pg_dump` / `psql` を実行します。
SQLite では URL が示すファイルをバックアップ／リストア対象にし、インメモリ SQLite の URL
は拒否します。

URL の上書きがない場合、PostgreSQL のバックアップ／リストアは管理対象コンテナが起動中なら
`docker exec` を使い、起動していなければ host 上の `pg_dump` / `psql` に fallback します。
SQLite では `config.sqlite.db_file_path` を対象にします。

## ローテーション

`MAX_BACKUPS_PER_DB = 3`（`repom/scripts/db_backup.py`）が、stem
（PostgreSQL は `postgres_db`、SQLite は DB ファイル名から拡張子を除いた部分）ごとの
保持世代数です。ローテーション対象は `backup_name_pattern(stem, suffix)`
（`_backup_utils.py`）が返す `<stem>_<8桁>_<6桁><suffix>` に
`re.fullmatch` で一致するファイルだけで、単純な glob ではなく厳密なパターンで
絞り込んでいます。これには次の4つの帰結があります。

1. per-database naming（repom#157）より前に書かれた、固定 stem `db_` の
   レガシーバックアップ（`db_<YYYYmmdd_HHMMSS>.sql.gz`）は、新しいパターンに
   一致しないため、ローテーションでも incomplete-file cleanup でも一切
   カウントされず、削除されません。
2. 例外: `postgres_db` が文字通り `"db"` の場合は、レガシーファイルの stem も
   `"db"` と一致するため新しいパターンにマッチし、通常どおりローテーション対象
   （＝3世代を超えた分の削除対象）に含まれます。
3. per-database naming への移行期間中は、レガシーファイルをすぐに消さず、
   新しい命名規則のバックアップが3世代そろうまで残してください。最初の
   新命名バックアップはレガシーバックアップの保持世代を引き継がないため
   （新パターンにマッチするファイルの数でローテーションが判断される）、
   1回目の新命名バックアップの直後にレガシーファイルを消すと、実質的な
   保持世代が一時的に1まで落ちます。
4. ローテーションは stem 単位です。ブランチ固有の DB 名やリネームされた DB は
   自分自身の3世代を独立して保持し、その DB 自体が使われなくなった後も
   ファイルは自動削除されずに残り続けます。

## リストア

```bash
uv run db_restore
```

`db_restore` はバックアップファイル名から `parse_backup_source_database()`
（`_backup_utils.py`）で元データベース名を読み取り、一覧表示・確認の両方で
使用します。

- 一覧はリストア先データベース自身のバックアップを先頭にまとめ、他データベース
  （または元データベースが不明なレガシーファイル）のバックアップはその後に
  続けて表示します。元データベースが不明なものは `[legacy/unknown source
  database]`、リストア先と異なるものは `[other database: <name>]` と表示されます。
- 確認方法もそれに応じて変わります。選択したバックアップの元データベースが
  リストア先と一致する場合は `[y/N]` の確認で足りますが、元データベースが
  不明または異なる場合は `y` の入力では進めず、リストア先データベース名を
  そのまま入力しないと実行されません。これにより、別環境のダンプを
  ワンキーで本番データベースへ流し込む事故を防いでいます。
- ローテーション節の例外と対になりますが、`postgres_db` が文字通り `"db"` の
  場合は `parse_backup_source_database()` が常に `None` を返すため、自分自身が
  作成した最新のバックアップでも `[legacy/unknown source database]` 扱いとなり、
  `db_restore` は毎回 `y` ではなくリストア先データベース名の入力を要求します。

SQLite のリストアでは、既存の DB ファイルがある場合に
`restore_backup_<timestamp>.sqlite3` という safety copy を作成します。このファイルは
通常のバックアップローテーションの対象外で、自動削除されません。PostgreSQL の
リストアには自動 safety copy はありません。

PostgreSQL のリストアは
`psql --no-psqlrc --single-transaction -v ON_ERROR_STOP=1 -f -` または
`pg_restore --single-transaction` で実行されます。通常の SQL や custom-format の復元で
ステートメントが失敗すると、そのリストアの変更はロールバックされ、リストア前の状態が
保たれます。プレーン SQL ダンプに large object データが含まれる場合、large object の
処理を囲む `BEGIN` / `COMMIT` が psql の外側のトランザクションを途中で終了させることが
あります。repom のモデルは large object を使用せず、`bytea` 列には影響しません。
custom-format の復元は `pg_restore --single-transaction` を使うため、この制限の対象外です。

## 失敗時の挙動

`db_backup.main()` と `db_restore.main()` は、失敗時にエラーメッセージを
表示・ログ出力したうえで例外を送出して終了します
（`repom.scripts._backup_utils.BackupError` / `RestoreError`、いずれも
`RuntimeError` のサブクラス）。呼び出し元プロセスの終了コードは非ゼロになるため、
タスクの成否を記録するスケジューラ（fast-domain の arq cron など）は、
失敗したバックアップ/リストアを失敗タスクとして正しく記録できます。
ただし PostgreSQL path では `ensure_backup_dir()` と `postgres_tls_settings()` が
wrapping try の外で実行されるため、`OSError` / `ValueError` が
`BackupError` / `RestoreError` に wrap されずに発生する場合があります。いずれも
コマンドの終了コードは非ゼロです。
（`db_restore` でユーザーが `q` または確認プロンプトで中断した場合は例外にはならず、
正常終了として扱われます。）

## 関連資料

- [`repom/scripts/db_backup.py`](../../../repom/scripts/db_backup.py)
- [`repom/scripts/db_restore.py`](../../../repom/scripts/db_restore.py)
- [`repom/scripts/_backup_utils.py`](../../../repom/scripts/_backup_utils.py)
- [README.md](../../../README.md) のコマンド一覧
