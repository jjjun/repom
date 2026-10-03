# repom セキュリティレビュー共通チェックリスト（ひな形）

状態: **暫定版 / 試行運用中**。使いながら不要な項目や足りない観点を見直します。

作成日: 2026-10-03

作成時の参照 revision: `46f83821ba95c764f583a8ac9f24d8d3453bc3d6`

更新履歴:

- 2026-10-03: Draft を作成。
- 2026-10-03: ひな形レビューの指摘を取り込み、試行運用を開始。追跡先の明記、対象漏れの追加、
  確認範囲の軸の記録、動的検証に必要な環境、テスト対応表、項目の分担を反映。
- 2026-10-03: V02 の advisory 監査範囲、PostgreSQL 実機検証の限界、§7 の保留事項追跡を明確化。

この文書はレビューの観点と記録形式のひな形です。実施済みの監査結果でも、
全項目が安全だという宣言でもありません。各項目の初期状態は **未確認** です。
Claude と Codex で共通に使います。運用で分かった過不足は §5 の
「チェックリストへのフィードバック」に記録し、この文書へ反映します。

守るべき性質と信頼境界の正本は [SECURITY.md](../../../SECURITY.md)、
作業手順は [AGENTS.md](../../../AGENTS.md) です。対象パスの入れ子のポリシーも読みます。
この文書はそれらの制限を緩めず、既知の弱点を受容する根拠にもなりません。
Codex Security プラグインの有無にかかわらず使えますが、各実行環境で実際に使った
ツールと実施できなかった検証を記録してください。

現在の運用では、見つけた問題と保留事項は issuekit の issue で管理します。
公開リポジトリとしての扱い（結果の保存先・公開範囲、外部からの報告窓口）は未決定で、
§7 の保留事項として追跡します。決まるまでは、レビュー結果と指摘の詳細を issuekit の
issue と依頼への応答で扱い、リポジトリに結果ファイルを追加しません。

## 1. レビューの開始時に記録すること

| 項目 | 記入欄 |
| --- | --- |
| 実施日・担当・独立レビュアー | 未記入 |
| 使用したエージェント・モデル・ツール | 未記入。プラグインの有無と、実施できなかった検証も書く |
| レビュー種別 | 全体 / 差分 / 指定 issue の修正検証 / ポリシー整合性 |
| 対象 revision・差分の基点・未コミット変更 | 未記入 |
| 対象機能・公開 API・除外範囲と理由 | 未記入 |
| SECURITY.md と本チェックリストの revision | 未記入 |
| Python・SQLAlchemy・Alembic・driver の実使用バージョン | 未記入 |
| uv.lock と実環境の一致・basekit の実使用 commit | 未記入 |
| 確認できる環境 | 未記入。OS、DB backend と driver、同期/非同期、CLI/Python API、host/Docker |
| 入力を制御できる主体・利用側アプリの露出・守る資産 | 未記入。分からない点は仮定として明記 |
| 元の指摘・関連 issue・過去に保留した事項 | 未記入。issuekit と §7 で現状を確認 |
| 利用側への影響と通知 | 未記入。mine-py / fast-domain などの取り込み状況と送付した提案 ID |

全体レビューでは全 ID を結果表に載せます。差分レビューでは変更箇所の入口・共通ヘルパー・
呼び出し先を追い、影響する ID を選び、残りの範囲を明記します。
既存テスト一覧やこのひな形にない経路も、変更や入力の流れから必要なら追加します。

DB を操作する検証は [テストガイド](../testing/testing_guide.md) に従い、
専用 DB と一時領域を使います。`EXEC_ENV=test` という文字列だけで接続先を安全と判断せず、
実際の対象を確認します。実サービスへの接続、資格情報変更、復元、公開、issue 更新は
それぞれ依頼範囲に従います。

## 2. 状態と証拠の付け方

| 状態 | 意味・必要な記録 |
| --- | --- |
| 未確認 | 未着手、または必要な証拠が不足している。理由を書く |
| 確認済み | 記録した条件・範囲で期待する性質を確認した。根拠を必須とする。範囲は §5 の軸の表で示し、実施しなかった軸は未確認として残す |
| 要対応 | 破られる性質、再現条件、影響、修正候補、追跡先を記録する |
| 保留 | 検証や管理者判断を待つ。担当、追跡先、再確認条件または期限を記録する |
| 対象外 | 対象 revision にその経路が存在しない根拠を記録する。恒久的な除外ではない |

全体レビューで範囲を絞る場合は、対象外にせず管理者判断として保留にします。
SECURITY.md のとおり、新しい除外には管理者の明示的な判断が必要です。

状態とは別に、証拠を **静的確認 / 動的検証 / 両方** に分類します。
静的確認ではファイル・シンボル・revision、動的検証ではテスト名・コマンド・終了結果・
OS/driver・実DBか fake かを記録します。静的証拠だけで結論を出せる場合はその理由を記録し、
実動作の検証が必要な性質についてはコードを読んだだけで確認済みにしません。

テストは「既存テスト（未実行）」と「実行（コマンド・結果・skip の理由）」を分けて書きます。
テストがあることは、実行して成功したことの証拠になりません。skip されたテストは、
その軸を確認していない扱いです。

指摘の種別も分けます: **検証済み脆弱性 / 未検証候補 / 文書不整合 / 改善提案 / 管理者判断**。
未検証候補を安全扱いにしたり、文書の修正だけで元のコード上の問題が解消した扱いに
したりしません。重大度は入力主体、必要権限、露出、影響に基づいて説明します。

## 3. 共通チェック項目

表の「入口」は調査を始める場所であり、そのファイルだけ見れば十分という意味ではありません。
具体的な現在の契約は SECURITY.md と対象 revision の実装で照合します。

項目の分担: SQL の構文は生成元を問わず Q01、INI は A03、Compose・env・argv は O04、
クライアント側の TLS は C02、サービスの公開範囲・DB role・ファイル権限は O06、
バックアップファイルの扱いは O02、restore の意味と権限は O03 で扱います。
重なる場合は主担当の ID に結果を書き、他方からは関連 ID として参照します。

### クエリ・モデル・トランザクション

| ID | 確認する問い | 調査の入口 |
| --- | --- | --- |
| Q01 | 外部由来の値が SQL の構文にならないか。値の bind と、識別子・入れ子の SQL 文脈の引用を分けて確認したか。rotation SQL や init SQL などの生成 SQL も含める | `repom/repositories/`, `repom/custom_types/`, `repom/postgres/credentials.py`, `repom/postgres/manage.py`, `repom/alembic/reset.py`; 資料 R1/R2 |
| Q02 | 列名・ソート・lookup の制限が、単独文字列、list/tuple 内の文字列、default 値、再検索の経路でも働くか | `_core.py`, `_repository_base.py`, 同期/非同期 `get_or_create()` |
| Q03 | 値専用の引数と trusted expression の引数を特定したか。ID・等価条件・関連 lookup・bulk の各入口で契約が守られるか | `_repository_base.py`, `_soft_delete.py`, `repom/mixins/many_to_many.py` |
| Q04 | 呼び出し側の条件と論理削除の条件が保持されるか。FilterParams の未マップ項目（既定値を含む）が拒否されるか、`_build_filters` の override でその拒否が無効になる点を記録したか。通常取得、count、bulk、get_or_create、関連取得を混同していないか | 同期/非同期 repository、`_query_builder.py`, `_soft_delete.py`、soft-delete guide |
| Q05 | limit 未指定、offset、IN の要素数、LIKE、bulk 行数、eager load が利用側から制御されたときの負荷を評価したか | `_core.py`, `_query_builder.py`, `MatchColumn`, `listjson_filter`; 上限の欠如だけで脆弱性と断定しない |
| M01 | constructor や辞書入力で保護設定・メソッドを上書きできないか。更新対象、主キー、system columns の扱いは契約どおりか | `repom/models/base_model.py`, `dict_save(s)`, `get_or_create`, `add_related_item`, `bulk_update` |
| M02 | sensitive_fields と serializable_fields が重なる場合や、instance 属性が同名の場合も出力制限が保たれるか | `BaseModel.to_dict()` とその利用箇所。ログや外部 serializer への適用を別に確認 |
| M03 | NUL 等の検証がどの書き込み経路で働くか。Core/bulk、SQL 式、custom type、column_property の限界を記録したか | `repom/nul_bytes.py`, mapper events、同期/非同期 bulk update |
| T01 | 内部/外部 session の commit・rollback・flush・SAVEPOINT・merge の責任と、部分失敗後の状態が契約どおりか | repository の session 管理、`repom/database.py` |
| T02 | session の並行共有、例外、キャンセルでデータや接続の状態を取り違えないか。commit 中断時の不確実性を隠していないか | `DatabaseManager` と repository の実際の呼び出し経路。manager のテストだけで repository を検証済みにしない |

### 接続先・秘密情報

| ID | 確認する問い | 調査の入口 |
| --- | --- | --- |
| C01 | 同じ設定から ORM・Alembic・診断・backup/restore が実際にどこへ接続するか。host だけでなく port・database・user の上書きと優先順位も比較したか。`EXEC_ENV` の正規化（`prod`/`production`、大文字小文字・空白、未知の値の dev 扱い）が TLS・破壊的操作・命名・fixture の guard で一致するか | `repom/config.py`, `repom/exec_env.py`, `database.py`, `alembic/env.py`, `repom/scripts/pg_dump_tools.py`; 下の比較表を使う |
| C02 | TLS の要求が URL・connect_args・環境変数・driver 変換後も保たれるか。暗号化と相手の証明書/hostname 検証を区別したか | `database.py`, `config.py`, `_backup_utils.py`; SQLite / PostgreSQL / Redis / pgAdmin の適用差を記録。サービス側の公開範囲は O06 |
| C03 | 正常時と失敗時の repr・ログ・例外・例外 chain・CLI 出力に秘密が出ないか。不正 URL、percent encoding、query 内 DSN、子プロセス stderr も確認したか | `safe_db_url`, Alembic setup、`repom_info`, backup/restore、credential helpers |
| C04 | SQL ログ、結果行、QueryAnalyzer、デバッグ出力の保存内容と閲覧者を確認したか。hide_parameters を万能な秘匿処理と扱っていないか | `repom/logging.py`, `repom/diagnostics/`, `debug_repository_queries.py` |

接続先の比較は、同じテスト設定ごとに表を埋めます。URL 表示だけで一致と判断せず、
driver に渡る引数と子プロセスの argv/env を比較します。libpq の環境変数
（`PGHOST`、`PGSERVICE`、`PGSSLMODE` など）の影響も記録します。実接続が必要な条件は別途残します。
秘密の値は記録せず、ダミー値での一致判定または伏字を使います。

| 入口 | 設定・上書き元 | 最終 host / port / database / user | 上書きの扱い（反映/拒否/黙って無視） | TLS・認証情報の渡し方 | 証拠・未確認点 |
| --- | --- | --- | --- | --- | --- |
| 同期 ORM | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| 非同期 ORM | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| test fixture（同期/非同期） | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| Alembic / AlembicReset | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| backup / restore CLI: host | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| backup / restore CLI: Docker | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| `pg_dump_tools`（Python API。直接組み立てた `PgConnParams` を含む） | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| `repom_info` / `database_info` | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| Redis クライアント・`repom_info` の Redis probe | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |
| pgAdmin（servers.json） | 未記入 | 未確認 | 未確認 | 未確認 | 未確認 |

`repom#233` の再検証では、列挙した query key のテストは通っても、`port`・`dbname`・`user`
の query 上書きで接続先が食い違うケースが残りました。これは **repom#240** で追跡しています。
過去の列挙をコピーするだけでなく、対象 driver の実際の引数解釈を比較するための観点です。
現在の修正状況は issuekit とソースで再確認します。

### Discovery・Alembic・管理操作・ファイル

| ID | 確認する問い | 調査の入口 |
| --- | --- | --- |
| A01 | import、CONFIG_HOOK、migration hook、master-data、INI のコード実行設定に低信頼の入力が入らないか。prefix 検査の実効範囲は何か | `repom/utility.py`, `alembic/env.py`, `db_sync_master.py`, `db_create.py`, `list_models.py`, `repom_info.py`, `debug_repository_queries.py`, `basekit` の lock 対象。prefix を sandbox と扱わない |
| A02 | import 失敗・metadata 欠落・namespace/exclusion 設定が意図しない drop を生まないか。生成 migration を人が確認する手順があるか | `alembic/env.py`, Alembic setup/templates、`alembic.ini`; 資料 R3 |
| A03 | 生成 INI に検証済みの値を出力しているか。migration の対象 DB、version table/schema、version_locations と削除対象が一致するか | `repom/alembic/templates.py`, `setup.py`, `reset.py` |
| O01 | 破壊的操作ごとの確認・環境制限・対象選択を確認したか。CLI の guard を Python API にまで一般化していないか | `db_delete`, `alembic_reset`, `db_restore`, `db_sync_master`, service remove、credential rotation、`pg_restore_custom` |
| O02 | バックアップ名と出力パス、symlink、partial file、失敗時 cleanup、既存ファイル、保持世代が対象範囲を逸脱しないか | `_backup_utils.py`, `db_backup.py`, `db_restore.py`, `pg_dump_tools.py`; Windows と POSIX を分ける |
| O03 | checksum 不一致/欠落と真正性の違い、SQL backup の実行権限、復元先を確認したか | backup/restore。checksum を署名や安全な SQL の証明と扱わない |
| O04 | Compose・env・argv の生成値が別の設定やオプションにならないか。image/name/volume/bind path と subprocess の option 解釈も確認したか（SQL は Q01、INI は A03） | `docker_compose_safety.py`, PostgreSQL/Redis manage、credential helpers |
| O05 | rotation の事前検証、live 変更後の保存失敗、復旧手順、上書き指定、backup copy の秘密保護を確認したか | PostgreSQL/Redis/pgAdmin の各経路。fake の成功だけで実サービスの復旧を検証済みにしない |
| O06 | 公開 port、DB role、生成 secret の初期/最終権限と Windows ACL の範囲が適切か（クライアント側 TLS は C02） | PostgreSQL/Redis/pgAdmin 設定、生成物、配布 template; 資料 R4。利用側の運用が不明ならそのまま記録 |

### テスト・依存関係・運用

| ID | 確認する問い | 調査の入口 |
| --- | --- | --- |
| V01 | テストが使う実際の DB・ファイルは隔離されているか。fixture gate や環境名だけに依存していないか | `repom/testing.py`, `tests/conftest.py`, `tests/session_config.py` |
| V02 | lock と実行環境が一致するか。実行環境と lock 全体の advisory 監査を区別し、platform marker と選択した extras/groups の範囲を記録したか。advisory 確認と git 依存の source review を区別したか | `pyproject.toml`, `uv.lock`, dependency-audit workflow。監査ツールの失敗/未実行、skip、未監査項目を0件としない。コマンドは §4 |
| V03 | 修正前に失敗し修正後に成功する回帰テストと、正当な利用を維持するテストがあるか | 対象 issue の元の再現、変更した共通処理と各入口。修正前の確認方法は §4 |
| V04 | sync/async、SQLite/PostgreSQL、CLI/Python API、host/Docker、Windows/POSIX の確認範囲を分けたか。skip と fake と実機の差を残したか | 対象テストと `.github/workflows/test.yml`。CI 定義と実行結果も区別 |
| V05 | issue の完了理由に修正証拠があり、文書修正・改善提案・判断待ちを取り違えていないか | issuekit の原文、受け入れ条件、実装・独立レビュー記録、残件の追跡先 |
| V06 | SECURITY.md、公開ガイド、breaking change の release note が実装と一致するか | `SECURITY.md`, `docs/guides/`, `docs/release_notes.md` |
| V07 | SECURITY.md に書かれた既知の制限・欠陥・未決事項ごとに、追跡 issue、管理者判断、送付済み提案のどれかを参照できるか。completed issue の残件と outgoing 提案の状態を確認したか | `SECURITY.md`, `issuekit queue`, `issuekit show <id>`, `issuekit outgoing --to <project>`, §7 |
| V08 | CI と開発用の自動実行（workflow の permissions、action の SHA 固定、SessionStart hook、pre-commit、MCP 設定、VS Code task）が意図しないコマンド実行や秘密の露出を生まないか | `.github/`, `.claude/hooks/session-start.sh`, `.claude/settings.json`, `.codex/config.toml`, `.mcp.json`, `.pre-commit-config.yaml`, `.vscode/tasks.json` |

## 4. 検証コマンドを選ぶための入口

これは一括実行リストではありません。選んだ ID と変更内容に応じてテストを選び、
実施記録には完全なパスを含むコマンドを書きます。
下の表はテストファイルが存在することを示すだけで、合否は実施記録に書きます。
ファイル名は、注記がなければ `tests/unit_tests/` 配下です。

| 観点 | 既存テスト |
| --- | --- |
| Q | `test_repository_ordering.py`, `test_order_by_introspection.py`, `test_repository.py`, `test_async_repository.py`, `test_find_by_ids.py`, `test_soft_delete.py`, `test_filter_string_matching.py`, `test_repository_pagination_limits.py`, `test_repository_options.py` |
| M | `test_sensitive_fields.py`, `test_update_from_dict.py`, `test_nul_byte_validation.py`, `test_many_to_many_mixin.py`, `custom_types/` |
| T | `test_repository_session_isolation.py`, `test_external_session_commit.py`, `test_soft_delete_external_session.py`, `test_internal_session_rollback.py`, `test_async_database.py` |
| C | `test_database_engine_settings.py`, `test_config_postgres.py`, `test_exec_env.py`, `test_config_hooks_*.py`, `test_config_engine_kwargs.py`, `test_redis_config_connection.py`, `test_database_url_masking.py`, `test_credential_repr_masking.py`, `test_no_raw_dsn_in_raise_messages.py`, `test_repom_info.py`, `test_sqlalchemy_echo_logging.py`, `test_query_analyzer.py`, `test_debug_repository_queries.py`, `test_logging.py`, `test_pg_dump_tools.py` |
| A | `test_alembic_setup.py`, `test_alembic_templates.py`, `test_alembic_env.py`, `test_alembic_reset.py`, `test_alembic_reset_script.py`, `test_alembic_init_script.py`, `test_auto_import_models.py`, `test_list_models.py`, `test_db_create.py`, `test_db_sync_master.py`, `test_external_project_alembic.py`, `tests/behavior_tests/` |
| O | `test_db_delete.py`, `test_db_backup.py`, `test_db_restore.py`, `test_backup_utils.py`, `test_pg_dump_tools.py`, `test_postgres_credentials.py`, `test_redis_credentials.py`, `test_postgres_manage.py`, `test_redis_manage.py`, `test_postgres_container_config.py`, `test_docker_service.py`, `test_docker_compose_safety.py` |
| V | `test_create_test_fixtures_safety.py`, `test_testing_engine_settings.py`, `test_pytest_configuration.py`, `test_env_example.py` |
| PostgreSQL 実機 | `tests/integration_tests/test_postgres_integration.py`（同期 psycopg）, `tests/integration_tests/test_utc_datetime_postgres.py`（UTCDateTime の同期/非同期 round trip。CI の PostgreSQL job は実行しない）。`DB_TYPE=postgres` と起動中の PostgreSQL がなければ skip |

動的検証に必要な環境:

| 環境 | 主な ID | 実行方法・注意 |
| --- | --- | --- |
| PostgreSQL | C01（同期 ORM の接続先のみ）, A02, M03, O03, Q04 | AGENTS.md の `docker run` で起動し、`CONFIG_HOOK=repom.config_hook:hook_config EXEC_ENV=test DB_TYPE=postgres POSTGRES_PASSWORD=<test password> uv run pytest tests/integration_tests/test_postgres_integration.py`。未設定だと全件 skip になり、確認済みの根拠にならない。このコマンドは同期 psycopg のみ |
| Docker | O04, O05, O06, backup/restore の Docker 経路 | 実サービスの起動・資格情報変更・復元は依頼範囲に従う。fake の成功で代えない |
| POSIX | O02, O06 | Windows では権限・symlink のテストが skip になる（2026-10-03 時点で 10 件）。CI（Ubuntu）の結果で補う場合は run を記録する |
| Windows | O06 | repom は ACL を設定しない。実際の権限は `icacls <path>` で確認する |
| ネットワーク・GitHub | V02, V04 | V02 の audit run は §4 の手順で対象 lock 内容と日付を確認する。V04 の CI run 確認には `gh run list --branch main`（認証が必要）を使える |

依存関係の確認（V02）では、整合性確認と advisory 監査を分けて記録します。
`uv lock --check` は lock と `pyproject.toml` の一致を、
`uv sync --locked --check` は現在の実行環境と lock の一致を確認するもので、どちらも advisory audit ではありません。

- 実行環境の advisory: `uv run pip-audit` は現在インストールされている実行環境を監査します。
  その成功を lock 全体の監査結果として扱いません。
- lock-wide advisory: 正規の lock 全体監査手順は [`.github/workflows/dependency-audit.yml`](../../../.github/workflows/dependency-audit.yml) です。
  完了した GitHub Actions の「Dependency audit」実行記録を開き、対象 revision で `uv.lock` を最後に変更した commit を確認します。
  その lock 内容と一致する run を選び、commit と監査日を記録します。advisory database は時間とともに変わるため、同じ lock 内容でも監査日は必要です。
  一致する run がなければ証拠なしと記録します。明示的に依頼されていない workflow の手動 dispatch は行いません。
  workflow は `--all-extras --dev` で同期し、実行環境の監査に加え、marker を除去した export に対して
  `uv run pip-audit -r requirements-audit.txt --no-deps --disable-pip` を実行します。
  export の `basekit @ git+...@<sha>` と `-e .` は workflow の `==` 件数に含まれず、監査対象になったと推測しません。
  skip された Git 依存を脆弱性なしと扱わず、監査した scope、未監査/skip package、失敗、取得できなかった証拠を記録します。
  `basekit` の lock 済み commit に対するソースレビューは advisory 監査と別の証拠です。

`tests/integration_tests/test_postgres_integration.py` は同期 psycopg の統合テストだけを含み、
基本接続と CRUD、設定された database への同期 ORM の接続先確認（`test_config_url_matches_connection` と `test_database_name`、C01 の一部）、plain SQL restore の失敗時 rollback（O03）、custom type を含む revision の PostgreSQL 上での自動生成（A02）、
JSON NUL escape の text extraction（M03）、PostgreSQL 上の `listjson_filter` の検索一致（Q04）を確認します。
`.github/workflows/test.yml` の PostgreSQL job もこのファイルだけを実行します。
C02 の TLS 証明書/hostname 検証による接続拒否、UTCDateTime round trip を超える asyncpg の接続挙動、session の並行共有、commit 中の cancellation（T02）は別の証拠が必要で、
証拠がなければ未確認です。`test_utc_datetime_postgres.py` の非同期 UTCDateTime round trip はそのテスト範囲だけの証拠で、
この CI job では実行されず、TLS identity や cancellation の証拠にもなりません。

修正前の確認（V03）: `git worktree add <一時ディレクトリ> <基点 revision>` で隔離した checkout を作り、
新しいテストだけを置いて実行します。共有 checkout で stash や checkout による巻き戻しはしません。
終わったら `git worktree remove <一時ディレクトリ>` で片付けます。

変更を実装した場合の共通チェックは `uv run pytest`、`uv run ruff check .`、
`uv run issuekit check-encoding --gate`、`git diff --check` です。
テストの追加・実行方法はテストガイド、issue の手順はその時点の issuekit protocol に従います。

## 5. 実施結果のひな形

本ファイルを結果で上書きしません。結果は依頼された保存先や応答にこの形式で書きます。
§7 の保存先が決まるまでは、issuekit の issue と依頼への応答を使います。
秘密情報や詳細な攻撃手順を共通ポリシーに貼り付けません。

```markdown
## 対象と結論

- 対象 revision / 差分基点 / 実行環境:
- 対象範囲・前提・除外範囲:
- 結論と残件:

## 項目別の結果

| ID | 状態 | 適用する入口・条件 | 証拠（静的/動的） | 未確認点・追跡先 |
| --- | --- | --- | --- | --- |
| 対象IDを列挙 | 未確認 | | | |

証拠の書き方: `既存テスト（未実行）: <path>::<name>` / `実行: <command> → N passed, M skipped（理由）` / `静的: <file>:<line> @ <revision>`

## 確認範囲の軸

凡例: 動＝動的に確認、静＝静的に確認、未＝未確認、—＝該当なし

| ID | 同期 | 非同期 | SQLite | PG/psycopg | PG/asyncpg | CLI | Python API | host | Docker | Windows | POSIX |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 対象ID | | | | | | | | | | | |

## 指摘（指摘ごとに記入）

- 種別・関連 ID・既存 issue:
- 入力を制御できる主体、入力から問題の操作までの経路:
- 破られる性質、前提条件、影響、重大度の理由:
- 対象 revision・source location・安全な再現の証拠:
- 反証・未確認点:
- 修正方針・受け入れ条件・正常系の維持:
- 追跡先（issuekit の issue ID）:

## 検証結果

| コマンド/検証 | revision・OS・backend/driver | 結果 | fake/実機・skip・限界 |
| --- | --- | --- | --- |
| 未記入 | | 未実行 | |

- 修正前の失敗 / 修正後の成功 / 正常系の維持:

## 保留と引き継ぎ

| 保留事項 | 担当/決定者 | 追跡先 | 再確認条件または期限 |
| --- | --- | --- | --- |
| 未記入 | | | |

- 今回見ていない範囲:
- 次回レビューの対象:

## チェックリストへのフィードバック

- 不要だった・重複していた項目:
- 足りなかった観点や経路:
- 実行できなかった確認方法と理由:
- 表現を直したほうがよい箇所:
```

issue が completed でも、元の受け入れ条件と残件を照合します。
判断待ちを別 issue に切り出す場合は、元 issue と追跡先の対応、担当、判断条件を残します。
元 issue が完了後に編集できない場合は、新 issue 側に元の番号と残件を明記します。
報告窓口（repom#234 から repom#241 へ切り出し）のように、未決定という記述だけで
追跡が途切れないようにします。
修正済み issue の検証結果はその問題の範囲に限り、リポジトリ全体の安全認定にしません。

## 6. 定期利用の案（未確定）

| 契機 | レビュー範囲の案 |
| --- | --- |
| セキュリティに関係する変更・release 前 | 差分と、変更した共通処理を使う各入口 |
| SQLAlchemy・Alembic・driver・basekit の更新 | 依存差分、実効設定、対応する契約・テスト・参照資料 |
| 定期レビュー | 全項目、過去の保留、公開経路や運用前提の変化 |

頻度と担当は初回利用後に決めます。現在の dependency audit と、ソースの定期レビューは
別の確認です。この案はスケジュールや自動実行を設定しません。

## 7. 保留事項

管理者の判断を待っている事項です。判断が出たら、この表と関連する節を更新します。
issuekit に判断待ち専用 stage はなく、未割当 issue は claim 可能です。repom#241 と repom#243 の decision gate に従い、
管理者が決める前に判断や実装を進めません。

| 保留事項 | 決定者 | 追跡先 | 現在の扱い | 再確認の契機 |
| --- | --- | --- | --- | --- |
| レビュー結果の保存先と公開範囲（リポジトリは public） | 管理者 | repom#243 | 指摘は issuekit で管理し、リポジトリに結果ファイルを追加しない | public として運用する準備を始めるとき、または issuekit 外に結果を保存または共有する必要が生じたとき |
| 外部からの脆弱性報告窓口 | 管理者 | repom#241 | 未設定 | 上と同じ。または本チェックリストの次回見直し |
| 動的検証の実行環境（PostgreSQL・Docker・POSIX） | 管理者 | repom#243 | 実施できない検証は未確認として残す | 初回の全体レビュー後、または利用可能な live 環境が必要になったとき |
| 独立レビュアーの条件 | 管理者 | repom#243 | issuekit の分離（実装者とレビュアーは別セッション）に従う。追加条件は未決定 | 初回利用後、または独立承認条件が必要になったとき |
| 定期レビューの頻度と担当 | 管理者 | repom#243 | §6 は案のみ。頻度・担当・自動化は未設定 | 初回利用後、または定期実行を導入する前 |

## 8. 参照資料と更新

外部資料の確認日: 2026-10-03。作成時の lock は SQLAlchemy 2.0.51 / Alembic 1.18.5 です。
リンク先は更新されるため、記載内容を実使用バージョンに照合してください。
第三者スキルのインストールを前提にせず、公式資料と repom の実装を根拠にします。

| ID | 資料 | 用途 |
| --- | --- | --- |
| R1 | [SQLAlchemy: Sending Parameters](https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html#sending-parameters) | SQL の値と bind の確認 |
| R2 | [OWASP: SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) | bind、識別子の allowlist、最小権限 |
| R3 | [Alembic: Autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) | migration の手動確認と検出限界。`alembic check` はセキュリティスキャナーではない |
| R4 | [OWASP: Database Security](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html) | 接続、権限、秘密情報、バックアップの運用確認 |

公開 API・default・driver・信頼境界が変わったとき、レビューで見落としが判明したとき、
または §5 のフィードバックがたまったときに項目を見直します。
項目の追加・統合・削除には理由を更新履歴に残し、既存 ID を別の意味に再利用しません。

## 9. チェックリスト自体の見直し依頼

次の依頼文は、このチェックリスト自体を評価するためのものです。

```text
AGENTS.md と SECURITY.md を読み、
docs/guides/security/security_review_checklist.md の暫定版をレビューしてください。

repom の現行コード・テスト・公開ガイドと、これまでの実施記録にある
「チェックリストへのフィードバック」に照らし、対象漏れ、誤った前提、
過剰な保証、実行できない確認方法、重複、保留事項の追跡漏れを確認してください。
同期/非同期、SQLite/PostgreSQL、CLI/Python API、host/Docker、Windows/POSIX の
違いが記録できるかも確認してください。

指摘にはチェック項目 ID、根拠の source location、問題になる理由、修正文案を付けてください。
既存テストがあることと、今回実行して成功したことを区別してください。
良好な項目、未確認の範囲、§7 の保留事項の現状も報告してください。
ファイルの修正、issue の作成・更新、監査全体の実行は
追加で依頼するまで行わず、レビュー結果を返してください。
```
