# Issue #074: runtime env override helper の対象拡張と利用プロジェクト向け提案

**ステータス**: ✅ 完了

**作成日**: 2026-05-22

**優先度**: 中

## 問題の説明

Issue #073 で PostgreSQL / pgAdmin の env override helper を追加したが、repom の config 周辺にはまだ環境変数で上書きできると便利、または既存資料が env 対応済みのように読める箇所が残っている。

調査で確認した主な不整合:

- `docs/guides/redis/redis_manager_guide.md` は `REDIS_HOST` / `REDIS_PASSWORD` / `REDIS_DB` を記載しているが、実装済み helper は `REDIS_PORT` のみを読む。
- 過去 Issue や PostgreSQL integration test は `DB_TYPE=postgres` を前提にしているが、現 `RepomConfig.db_type` は `DB_TYPE` を直接読まず、hook 側の明示設定が必要。
- `config.db_url` は setter を持つが、CI / PaaS で標準的な `DATABASE_URL` からの上書き helper がない。
- SQLAlchemy query logging は `config.enable_sqlalchemy_echo` / `config.sqlalchemy_echo_level` を持つが、一時調査用に env で切り替える公式 helper がない。
- SQLite は `SQLITE_USE_FILE_DB` を `RepomConfig.db_url` 内で直接読んでおり、他の env override helper と置き場所が非対称。

また、fast-domain / mine-py など repom 利用側は `CONFIG_HOOK` でプロジェクト固有設定を持つため、repom 側の helper 追加だけでは「既存 hook の末尾でどの helper を呼ぶべきか」が伝わらない。提案書として利用側変更を残す必要がある。

## 提案される解決策

`repom/config_hooks/` を runtime env override helper の置き場として拡張し、以下を追加または拡張する。

1. `repom/config_hooks/database.py`
   - `apply_database_env_overrides(config)`
   - `DATABASE_URL` / `REPOM_DATABASE_URL` -> `config.db_url`
   - `DB_TYPE` -> `config.db_type`
   - `SQLALCHEMY_ECHO` -> `config.enable_sqlalchemy_echo`
   - `SQLALCHEMY_ECHO_LEVEL` -> `config.sqlalchemy_echo_level`
2. `repom/config_hooks/redis.py`
   - 既存 `REDIS_PORT` に加えて `REDIS_HOST` / `REDIS_PASSWORD` / `REDIS_DB` を読む。
3. `repom/config_hooks/sqlite.py`
   - `apply_sqlite_env_overrides(config)`
   - `SQLITE_DB_PATH` / `SQLITE_DB_FILE` / `SQLITE_USE_IN_MEMORY_FOR_TESTS` を読む。
   - 既存の `SQLITE_USE_FILE_DB` は互換性のため維持しつつ、helper 側へ寄せる。
4. `repom/config_hook.py`
   - repom 自身の hook で database / postgres / pgadmin / redis / sqlite helper を呼ぶ例を追加。
5. docs 更新
   - CONFIG_HOOK guide
   - Redis guide / README
   - PostgreSQL setup guide
   - testing guide の SQLite env 記述
6. proposals 作成
   - fast-domain: hook 末尾で新 helper 群を呼ぶ提案
   - mine-py: hook 末尾で新 helper 群を呼ぶ提案

## 影響範囲

- `repom/config_hooks/`
- `repom/config_hook.py`
- `repom/config.py` (`SQLITE_USE_FILE_DB` 直読みの整理)
- `tests/unit_tests/test_config_hooks_*.py`
- `docs/guides/features/config_hook_guide.md`
- `docs/guides/redis/redis_manager_guide.md`
- `docs/guides/redis/README.md`
- `docs/guides/postgresql/postgresql_setup_guide.md`
- `docs/guides/testing/testing_guide.md`
- `docs/proposals/`

## 実装計画

1. env parsing helper を小さく実装する（bool / int / port）。
2. database / sqlite helper を追加し、redis helper を拡張する。
3. `RepomConfig.db_url` 内の `SQLITE_USE_FILE_DB` 直読みを helper 適用後の config state 参照へ寄せる。
4. repom 自身の `config_hook.py` に helper 呼び出しを追加する。
5. unit test を追加・更新する。
6. guides と README を実装内容に合わせて更新する。
7. fast-domain / mine-py 向け proposal を作成する。
8. `uv run pytest` で確認する。
9. 完了後、Issue を `completed/` へ移し `docs/issues/README.md` を更新する。

## テスト計画

- database helper:
  - env 未設定時に何もしない。
  - `DATABASE_URL` / `REPOM_DATABASE_URL` の優先順位。
  - `DB_TYPE` の正常値・不正値。
  - bool env の正常値・不正値。
  - SQLAlchemy echo level の正常値・不正値。
- redis helper:
  - `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` / `REDIS_DB` の個別・複合適用。
  - port / db の非整数・範囲外。
- sqlite helper:
  - `SQLITE_DB_PATH` / `SQLITE_DB_FILE` / `SQLITE_USE_IN_MEMORY_FOR_TESTS`。
  - `SQLITE_USE_FILE_DB` 互換挙動。
- singleton reload:
  - repom 自身の `CONFIG_HOOK` 経由で helper が適用されること。

## 関連リソース

- `repom/config.py`
- `repom/config_hook.py`
- `repom/config_hooks/redis.py`
- `repom/config_hooks/postgres.py`
- `repom/config_hooks/pgadmin.py`
- `docs/proposals/002_fast_domain_call_repom_redis_env_helper.md`
- `docs/guides/features/config_hook_guide.md`
- `docs/guides/redis/redis_manager_guide.md`
- `docs/guides/postgresql/postgresql_setup_guide.md`
