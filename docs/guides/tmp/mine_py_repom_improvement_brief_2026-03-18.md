# mine-py 向け repom 利用改善書（A/B/C 対応）

- 作成日: 2026-03-18
- 作成元: repom プロジェクト監査
- 対象プロジェクト: mine-py
- 目的: repom 利用の安定性・保守性・運用整合性を高める

## 0. この資料の位置づけ

本資料は、次の3項目に限定した「調査結果 + 改善提案」です。

1. A. repom.database._db_manager（private API）への依存
2. B. Repository 層で session.query / session.execute(select(...)) の直接利用が多い
3. C. docs 上の旧名称 mine_db 記述

実装は含みません。mine-py 側の設計判断と実施計画づくりに使う前提です。

## 1. エグゼクティブサマリ

- A は将来互換性リスクが高く、最優先で縮小推奨
- B は「API 検索の find」と「内部処理の固定クエリ」を分離する運用明文化が必要
- C はコード影響は低いが、運用手順の誤読リスクを下げるため早期修正が望ましい

推奨実施順:

1. A（private API 依存の縮小）
2. B（Repository クエリ方針の明文化と段階是正）
3. C（docs 文言統一）

## 2. A. _db_manager（private API）依存

### 2.1 調査結果

mine-py の複数箇所で次の private API 利用を確認。

- from repom.database import _db_manager
- with _db_manager.get_sync_transaction() as session:

主な確認箇所（例）:

- src/domains/ani_dani/tasks/ani_dani.py
- src/domains/ani_niconico/tasks/ani_niconico.py
- src/domains/ani_video/tasks/ani_video.py
- src/domains/ani_wiki/tasks/ani_wiki.py
- src/domains/voicescript/api/voice_generation_job_routes.py
- src/domains/voicescript/api/voice_script_line_log_routes.py

### 2.2 リスク

- private API は公開互換性の対象外になりやすく、repom 更新時に破壊的変更の影響を受けやすい
- mine-py の repom 追従コストが増える

### 2.3 改善方針

- 原則: 公開 API（例: get_standalone_sync_transaction など）を優先
- 例外: private API が必要な箇所は「理由」と「置換条件」を明記

### 2.4 実施ステップ

1. private API 利用箇所を一覧化（すでに粗抽出済み）
2. 各箇所を公開 API へ置換可能か判定
3. 置換可能箇所から段階移行
4. 残件には TODO コメントと issue を付与

### 2.5 完了条件

- 新規コードで _db_manager の直接 import を禁止
- 既存コードの依存箇所が管理可能な最小数まで減少

## 3. B. Repository 層の直接クエリ利用

### 3.1 調査結果

BaseRepository / AsyncBaseRepository 継承は広く採用されている一方、Repository 内で次の直接クエリが多数。

- self.session.query(...)
- self.session.execute(select(...))

代表例:

- src/domains/ani_video/repositories/ani_video_item.py
- src/domains/ani_wiki/repositories/ani_wiki_change_log.py
- src/domains/timeblocks/repositories/*
- src/domains/voicescript/repositories/*

### 3.2 方針（重要）

- find は主に API 経由検索で利用する
- 内部処理（同期、バッチ、整合性更新）では原則 find を使わない
- 内部処理は「結果が固定される専用メソッド」または「明示クエリ」を使う

補足:

- find 自体を禁止する意図ではない
- 内部で find を使う場合は、固定パラメータのみを利用し、検索契約（順序、件数、フィルタ条件）を明記する

### 3.3 改善方針

- mine-py 内規として「find 利用範囲」と「直接クエリ許容条件」を1ページで定義
- PR レビュー時に次を確認
  - API 検索なのか、内部処理なのか
  - 内部処理で find を使っていないか（使う場合は契約が明記されているか）
  - 複雑ケースで直接クエリを使う理由がコメント化されているか

### 3.4 実施ステップ

1. Repository ガイド（mine-py docs）に判定基準を追加
2. 代表ドメイン1つで試験適用（例: ani_video）
3. 効果確認後に他ドメインへ展開

### 3.5 完了条件

- 新規 Repository 実装で API 検索と内部処理の使い分け基準が守られる
- 「何を直接クエリにするか」の揺れが減る

## 4. C. docs の旧名称 mine_db 記述

### 4.1 調査結果

コード import で旧パッケージ名利用は確認されない一方、docs に旧名称由来の記述が残存。

確認例:

- docs/guides/development/alembic_guide.md
- docs/guides/domain/timeblocks/system_guide.md

### 4.2 リスク

- 新規参加者が古いパス/運用を参照する可能性
- 手順ミス（DB ファイル場所の誤認）

### 4.3 改善方針

- docs 全体を横断し mine_db 記述を現行名称へ統一
- 変更時に「旧名称→新名称」の対応表を短く添える

### 4.4 実施ステップ

1. docs 横断検索で mine_db を全件抽出
2. 実態に合わせて修正
3. レビューで運用手順との一致確認

### 4.5 完了条件

- mine-py 直下 docs で mine_db 記述ゼロ
- DB パス説明が現行構成と一致

## 5. 推奨ロードマップ（2スプリント想定）

### Sprint 1（安全性優先）

1. A の対応方針確定
2. private API 依存の高頻度実行パスを先行置換
3. B の「直接クエリ許容条件」ドキュメント作成

### Sprint 2（一貫性優先）

1. B を主要2ドメインで適用
2. C の docs 文言統一を完了
3. 運用ルールを PR テンプレートに反映

## 6. mine-py 側へ引き渡す際の要約

- A: _db_manager 依存は将来互換性の観点で優先削減
- B: find は API 検索中心、内部は固定クエリ中心という運用で統一
- C: mine_db 記述はコードではなく docs に残存、運用事故防止のため更新推奨

以上。
