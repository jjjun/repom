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

- PostgreSQL: `<data_path>/backups/postgres/<接続先の DB 名>_<YYYYmmdd_HHMMSS>.sql.gz`
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

`config.db_url_overridden` が真の場合、PostgreSQL のバックアップ stem は URL の database 名、
SQLite の stem は URL が示すファイル名になります。URL の backend が SQLite / PostgreSQL
以外なら `db_backup` は `BackupError`、`db_restore` は `RestoreError` を
`Unsupported database type` のメッセージで送出します。PostgreSQL URL に host、user、
database のいずれかがない場合は、`PgConnParams.from_config()` が `ValueError` を送出します。

URL override を使う PostgreSQL の host-side client tool も、prod 環境の TLS policy を適用した
有効 URL の値で接続します。remote host で `sslmode` が未指定なら `require` が補われ、
設定済みの `sslrootcert` も有効 URL に追加されます。host がない URL は local 扱いです。
prod の remote host で弱い `sslmode` を指定すると、client process の起動前に拒否されます。
ただし、クライアントツールでは URL クエリの `host`、`hostaddr`、`service`、`dsn` による接続先の上書きを拒否し、URL authority の接続先を使います。`-d` に渡す DB 名も、libpq の接続文字列や URI として解釈される形式は拒否します。
詳しくは [PostgreSQL 実行時設定の上書き](../postgresql/runtime_env_overrides.md) を参照してください。

## ローテーション

`MAX_BACKUPS_PER_DB = 3`（`repom/scripts/db_backup.py`）が、stem
（PostgreSQL は接続先 DB 名、URL override 時は URL の database 名、SQLite は DB ファイル名から
拡張子を除いた部分）ごとの
保持世代数です。ローテーション対象は `backup_name_pattern(stem, suffix)`
（`_backup_utils.py`）が返す `<stem>_<8桁>_<6桁><suffix>` に
`re.fullmatch` で一致するファイルだけで、単純な glob ではなく厳密なパターンで
絞り込んでいます。これには次の4つの帰結があります。

1. per-database naming（repom#157）より前に書かれた、固定 stem `db_` の
   レガシーバックアップ（`db_<YYYYmmdd_HHMMSS>.sql.gz`）は、新しいパターンに
   一致しないため、ローテーションでも incomplete-file cleanup でも一切
   カウントされず、削除されません。
2. 例外: 接続先の PostgreSQL DB 名が文字通り `"db"` の場合は、レガシーファイルの stem も
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
- ローテーション節の例外と対になりますが、接続先の PostgreSQL DB 名が文字通り `"db"` の
  場合は `parse_backup_source_database()` が常に `None` を返すため、自分自身が
  作成した最新のバックアップでも `[legacy/unknown source database]` 扱いとなり、
  `db_restore` は毎回 `y` ではなくリストア先データベース名の入力を要求します。

SQLite のリストアでは、既存の DB ファイルがある場合に
`restore_backup_<timestamp>.sqlite3` という safety copy を作成します。このファイルは
通常のバックアップローテーションの対象外で、自動削除されません。PostgreSQL の
リストアには自動 safety copy はありません。

`db_restore` は PostgreSQL の gzip 圧縮したプレーン SQL (`.sql.gz`) だけを `psql` で
復元します。`psql --no-psqlrc --single-transaction -v ON_ERROR_STOP=1 -f -` を使うため、
通常の SQL でステートメントが失敗すると変更はロールバックされ、リストア前の状態が保たれます。
large object を含むプレーン SQL ダンプでは、large object の処理を囲む `BEGIN` / `COMMIT`
が psql の外側のトランザクションを途中で終了させる場合があります。repom のモデルは large
object を使用せず、`bytea` 列には影響しません。

## `pg_dump_tools` の library helper

`repom.scripts.pg_dump_tools` は custom-format の PostgreSQL dump / restore を行う
library helper を提供します。`PgConnParams.from_config()` は現在の設定から接続情報を作成し、
`pg_dump_custom()` と `pg_restore_custom()` はそれぞれ custom-format の dump と restore を
実行します。`pg_restore_custom()` は `pg_restore --single-transaction` を使用します。
`pg_tools_available()` は設定された経路で必要な client tools を利用できるか確認します。
これらは console script の `db_backup` / `db_restore` とは別の library API です。

## 失敗時の挙動

`db_backup.main()` と `db_restore.main()` は、失敗時にエラーメッセージを
表示・ログ出力したうえで例外を送出して終了します
（`repom.scripts._backup_utils.BackupError` / `RestoreError`、いずれも
`RuntimeError` のサブクラス）。呼び出し元プロセスの終了コードは非ゼロになるため、
タスクの成否を記録するスケジューラ（fast-domain の arq cron など）は、
失敗したバックアップ/リストアを失敗タスクとして正しく記録できます。
ただし PostgreSQL path では `ensure_backup_dir()` と `PgConnParams.from_config()` が
wrapping try の外で実行されるため、`OSError` / `ValueError` が
`BackupError` / `RestoreError` に wrap されずに発生する場合があります。`ValueError` は
`PgConnParams.from_config()` が読む `config.db_url` の TLS policy、または URL に host / user /
database がない場合の検査から発生します。いずれも
コマンドの終了コードは非ゼロです。
（`db_restore` でユーザーが `q` または確認プロンプトで中断した場合は例外にはならず、
正常終了として扱われます。）

## 関連資料

- [`repom/scripts/db_backup.py`](../../../repom/scripts/db_backup.py)
- [`repom/scripts/db_restore.py`](../../../repom/scripts/db_restore.py)
- [`repom/scripts/_backup_utils.py`](../../../repom/scripts/_backup_utils.py)
- [マスターデータ同期ガイド](master_data_sync_guide.md)
- [PostgreSQL 実行時設定の上書き](../postgresql/runtime_env_overrides.md)
- [README.md](../../../README.md) のコマンド一覧
