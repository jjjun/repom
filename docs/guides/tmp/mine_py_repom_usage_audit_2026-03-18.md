# mine-py における repom 利用監査レポート

- 作成日: 2026-03-18
- 監査対象: `C:\Users\jj\Desktop\workspace_main\projects\mine-py`
- 目的: 外部プロジェクトでの repom 利用が想定運用に沿っているか確認
- 監査方法: 読み取り専用（コード変更なし）

## 判定サマリ

総合判定: **概ね想定どおり（ただし一部改善推奨あり）**

- モデル/リポジトリを各ドメイン配下に配置する構成は、repom の「共有基盤 + 利用側でドメイン実装」の思想に合致
- `BaseModelAuto` / `BaseRepository` / `AsyncBaseRepository` の採用は広く確認
- 外部プロジェクトとしての `alembic.ini` 設定は想定どおり
- テストで `create_test_fixtures()` / `create_async_test_fixtures()` を利用しており、推奨方針に整合
- 一方で、private API 依存（`_db_manager`）と、Repository 層での `session.query` 直接利用が複数あり、将来互換性と統一性の観点で改善余地あり

## 期待値（repom 側ガイド）との照合

### 1. 利用側でモデル/Repositoryを持つ
- 期待: repom は共有基盤、アプリ固有モデルは利用側プロジェクトに配置
- 実態: `src/domains/*/models`, `src/domains/*/repositories` に配置
- 判定: **適合**

### 2. モデル定義（BaseModelAuto等）
- 期待: `BaseModelAuto` など repom 基底を継承
- 実態: 各ドメインで `BaseModelAuto` 継承クラスが多数
- 判定: **適合**

### 3. Repository パターン
- 期待: `BaseRepository` 系の活用を基本とし、データアクセスを Repository 層に集約
- 実態: ほとんどのドメインで `BaseRepository` / `AsyncBaseRepository` 継承を確認
- 判定: **概ね適合（要改善点あり）**

### 4. テスト方針
- 期待: `repom.testing.create_test_fixtures` ベースの fixture 利用
- 実態: `tests/conftest.py` で `create_test_fixtures()` と `create_async_test_fixtures()` を利用
- 判定: **適合**

### 5. 設定/環境
- 期待: `EXEC_ENV` と `CONFIG_HOOK` を利用
- 実態: `.env` と `tests/conftest.py` で設定確認
- 判定: **適合**

### 6. Alembic（外部プロジェクト）
- 期待: `alembic.ini` を単一ソースとして `version_locations = %(here)s/alembic/versions`
- 実態: `mine-py/alembic.ini` で期待どおり設定
- 判定: **適合**

## 改善推奨事項（重要度順）

### A. `repom.database._db_manager`（private API）への依存
- 重要度: **中〜高**
- 内容:
  - 複数タスク/一部 API で `from repom.database import _db_manager` を利用
  - `_` 始まりは内部実装であり、将来の破壊的変更リスクが高い
- 主な確認箇所:
  - `src/domains/ani_dani/tasks/ani_dani.py`
  - `src/domains/ani_niconico/tasks/ani_niconico.py`
  - `src/domains/ani_video/tasks/ani_video.py`
  - `src/domains/ani_wiki/tasks/ani_wiki.py`
  - `src/domains/voicescript/api/voice_generation_job_routes.py`
  - `src/domains/voicescript/api/voice_script_line_log_routes.py`
- 推奨:
  - 可能な範囲で公開 API（例: `get_standalone_sync_transaction` など公開関数）へ寄せる
  - private API 利用箇所を最小化し、利用理由をコメント/ドキュメント化

### B. Repository 層で `session.query` / `session.execute(select(...))` の直接利用が多い
- 重要度: **中**
- 内容:
  - `BaseRepository` を継承していても、個別メソッドで生 SQLAlchemy クエリを直接組み立てる箇所が散見
  - 高度クエリが必要な場面は妥当だが、単純取得まで混在すると規約・保守性の一貫性が低下
- 代表例:
  - `src/domains/ani_video/repositories/ani_video_item.py`（`find_by_title` が `session.query` 直接使用）
  - `src/domains/ani_wiki/repositories/ani_wiki_change_log.py`
  - `src/domains/timeblocks/repositories/*`
  - `src/domains/voicescript/repositories/*`
- 推奨:
  - 単純 CRUD/検索は `BaseRepository` 既存メソッドへ寄せる
  - 複雑クエリのみ直接クエリを許容するルールに整理
  - プロジェクトガイドへ「直接クエリ許容条件」を明記

### C. docs 上の旧名称 `mine_db` 記述
- 重要度: **低**
- 内容:
  - ドキュメントに旧パス名由来の `mine_db` 記述が一部残存
  - 実コードの import では旧パッケージ名利用は確認されず
- 確認例:
  - `docs/guides/development/alembic_guide.md`
  - `docs/guides/domain/timeblocks/system_guide.md`
- 推奨:
  - 運用資料として誤解を避けるため、現行パス/名称へ統一

## 適合している実装（ポジティブ確認）

- ドメインごとにモデル/Repository を配置する構成は、repom を shared foundation として使う想定に合う
- `src/mine_py/config_hook.py` で `model_locations` / `allowed_package_prefixes` / `model_excluded_dirs` を適切に設定
- `alembic.ini` の `version_locations` が外部プロジェクト向け推奨に一致
- テスト基盤は `repom.testing` の fixture 生成を採用しており、方針整合性が高い

## 結論

mine-py の repom 利用は、**設計レベルでは想定運用に沿っている**と判断できます。

改善優先度としては、まず
1) private API (`_db_manager`) 依存の縮小、
2) Repository 層の直接クエリ利用ルール整理、
3) docs の旧名称修正、
の順で進めるのが効果的です。

---

必要であれば次段として、上記 A/B について「最小変更での具体的リファクタリング候補ファイル一覧（差分方針のみ、実装なし）」を作成できます。
