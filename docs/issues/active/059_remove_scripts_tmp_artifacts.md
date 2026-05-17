# Issue #59: `repom/scripts/tmp/` 投資調査スクリプトの削除

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 中

## 問題の説明

`repom/scripts/tmp/` 配下に過去の SQLAlchemy 関係解決調査で作られたデバッグスクリプトが 4 ファイル残っている。

- `repom/scripts/tmp/investigate_eval_namespace.py`
- `repom/scripts/tmp/investigate_string_resolution.py`
- `repom/scripts/tmp/investigation_summary.py`
- `repom/scripts/tmp/reproduce_exact_error.py`

合計約 960 行。いずれもパッケージのエントリポイント（`pyproject.toml` の `[project.scripts]`）から参照されておらず、関連調査（#020 循環 import、#021 マッパー干渉、#022 isolated_mapper_registry など）はすでに完了している。

放置すると:
- 新規参加者が「現役の実装か調査の残骸か」判別できない
- パッケージング時に余計なファイルが含まれる
- grep ノイズになる

## 提案される解決策

`repom/scripts/tmp/` ディレクトリごと削除する。Git 履歴に経緯は残るため、調査内容を後から参照する必要があれば commit hash で辿れる。

## 影響範囲

- 削除: `repom/scripts/tmp/` 配下 4 ファイル
- 参照確認: 静的解析・grep でこれらのファイル名/モジュール名が他から参照されていないことを確認
- ドキュメント: 言及している箇所があれば削除（基本的にはないはず）

## 実装計画

1. `grep -r "scripts.tmp"` / `grep -r "investigate_eval_namespace"` 等で参照ゼロを確認
2. `repom/scripts/tmp/` を削除
3. `uv run pytest` で回帰がないことを確認

## テスト計画

- 既存テスト全件パス（unit + behavior）
- `uv build` でビルド成功
- `uv run repom_info` 等の CLI が問題なく動作

## 関連リソース

- 関連完了 Issue: #020, #021, #022, #029
