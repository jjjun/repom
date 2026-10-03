# PostgreSQL と pgAdmin の認証情報ローテーション

repom は新しい PostgreSQL / pgAdmin 認証情報を含む compose file を生成できますが、既存の
Docker volume には初期化時の認証情報が残ります。PostgreSQL のデータを削除せずに既存環境を
更新する場合は、以下の rotation helper を使います。

## PostgreSQL

console entry point の `main_postgres(argv)` は明示的な引数 list を受け取ります。
独自の option parser を使う task runner は `rotate_postgres_credentials_cli(...)` を keyword
引数で呼び出せます。console command と同じ password prompt、stdin、dry-run、実行経路を使います。

まず SQL plan を dry-run します。

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run postgres_rotate_credentials \
  --new-password-stdin \
  --current-password-stdin
```

mask された plan を確認してから実行します。

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run postgres_rotate_credentials \
  --new-password-stdin \
  --current-password-stdin \
  --execute
```

実行前に設定側の password holder を新しい password に更新してください。この時点では PostgreSQL
role の password はまだ古いため、上記のように `--current-password-stdin` で古い値を渡します。
設定側に古い password が残っている場合、current-password option を省略すると、その値を現在の
password として使います。TTY では設定済みの値を使うため、現在の password は prompt されません。
`--current-password` と `--new-password` は process argument に値が見えるため、対応する
`*-stdin` option を推奨します。両方の stdin option を使う場合、新しい password を先に読みます。
TTY で new-password option を省略すると、新しい値を prompt します。
`--allow-config-password` は設定済み password を新しい値として使う明示的な opt-in です。

password だけを変更する場合、要求された DB と schema の grant をすべて適用してから現在の role の
password を変更します。grant が失敗したときは現在の login 認証情報は変わりません。

`--database` は複数指定できます。既定では `db_name`、`db_name_dev`、`db_name_test` を対象とします。
`--schema` も複数指定でき、既定値は `public` です。

application role 自体を置き換える場合は次のように指定します。

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run postgres_rotate_credentials \
  --current-user repom \
  --current-password-stdin \
  --new-user mine_py_app \
  --new-password-stdin \
  --database mine_py \
  --database mine_py_dev \
  --database mine_py_test \
  --execute
```

replacement-user path は新しい role を作成または更新し、DB、schema、table、sequence、将来の default
privilege を付与します。古い role は削除しません。成功すると compose secret を再生成する前に
PostgreSQL の user と password の設定を両方更新します。

## pgAdmin

`main_pgadmin(argv)` は明示的な引数 list を受け取ります。task runner は
`rotate_pgadmin_credentials_cli(...)` を keyword 引数で呼び出すと、同じ password 解決と volume
再作成の処理を使えます。

repom は container 内で pgAdmin がサポートする `setup.py update-user --password` を使います。
pgAdmin の user 管理手順には password の stdin / environment からの入力方法がないため、実行中は
mask された repom 出力だけでは process argument への一時的な露出を防げません。まず dry-run します。

```bash
printf '%s\n' 'new-password' | uv run pgadmin_rotate_password --new-password-stdin
```

mask された command を確認してから実行します。

```bash
printf '%s\n' 'new-password' | uv run pgadmin_rotate_password --new-password-stdin --execute
```

この更新 command が利用中の image で使えない場合は、新しい `PGADMIN_DEFAULT_EMAIL` と
`PGADMIN_DEFAULT_PASSWORD` を設定し、pgAdmin volume だけを再作成できます。実行前に dry-run を
確認します。

```bash
uv run pgadmin_rotate_password --recreate-volume
uv run pgadmin_rotate_password --recreate-volume --execute --confirm-recreate-volume
uv run postgres_start
```

この手順は pgAdmin が保存した UI state を消しますが、PostgreSQL data volume は消しません。
`setup.py update-user --password` に新しい pgAdmin password を渡すことが許容できない場合にも使えます。

成功した rotation または確認済みの volume 再作成の後、repom は生成済み `.env` を設定済み password
で更新します。library function `rotate_postgres_credentials`、`rotate_pgadmin_password`、
`recreate_pgadmin_volume` も成功後の `.env` 更新を行うため、呼び出し側での追加保存は不要です。
secret が変わる場合は以前の file が `.env.bak` として残ります。

生成 compose file と `.env` の再生成や `--force-regenerate` の挙動は
[Docker manager ガイド](../features/docker_manager_guide.md)を参照してください。既存 volume の認証情報と
設定値が異なる場合は、対応する rotation command を使ってください。

## 注意事項

- PostgreSQL rotation は redacted な plan から表示用 SQL を生成し、引用符を含む password の SQL 内表現も表示・失敗 message に出しません。
- PostgreSQL の実行では現在の password の `PGPASSWORD` を `docker exec --env-file` で container に
  渡します。値は mode `0600` の一時 file に書かれ、rotation の終了時に削除されます。SQL は stdin
  経由で送るため、新しい password も `psql` の process argument に入りません。
- pgAdmin の `update-user` argv に関するものも含め、失敗時は raw subprocess traceback の代わりに
  password を mask した error が送出されます。
- `--execute` を指定する前に dry-run の内容を確認してください。
