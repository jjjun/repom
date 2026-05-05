# Issue #057: ログのアクティブファイルを日付付き形式に固定する

**ステータス**: ✅ 完了

**作成日**: 2026-05-05
**完了日**: 2026-05-05

**優先度**: 中

## 問題の説明

repom のロギングガイドは、ログファイルを `<区分>_<YYYY-MM-DD>.log` 形式で日次ローテーションし、当日のアクティブファイルも `main_2026-05-05.log` のような日付付きファイルに出力すると説明している。

一方、現行の `make_timed_rotating_handler(base_path)` は `TimedRotatingFileHandler(str(base_path), ...)` に拡張子なしの base path を渡しているため、起動中のアクティブファイルは `main` になる。これはガイド、fast-domain 移行メモ、consumer project で期待するファイル名と一致しない。

## 提案される解決策

`make_timed_rotating_handler()` の公開 API は維持しつつ、handler 内部で当日の日付付きファイルを開くようにする。

- `base_path=".../main"` から `.../main_<YYYY-MM-DD>.log` を生成する
- emit 時に日付が変わっていれば stream を切り替える
- `base_*.log` のうち古いファイルを `backup_count` に基づいて削除する
- `backup_count=0` の場合は削除しない

## 影響範囲

- `repom/logging.py`
- `tests/unit_tests/test_logging.py`
- `docs/guides/features/logging_guide.md`
- fast-domain の logging 移行で利用される `repom.logging.make_timed_rotating_handler`

## 実装計画

1. 日付付きアクティブファイルを扱う handler クラスを `repom/logging.py` に追加する。
2. `make_timed_rotating_handler()` から新 handler を返す。
3. 既存の get_logger / SQLAlchemy logging は公開 API を変えずに新 handler を使う。
4. unit test で active file 名、日付切り替え、古いログ削除、default logging setup を固定する。
5. logging guide の古い `main.log` 記述を修正する。

## テスト計画

- `poetry run pytest tests/unit_tests/test_logging.py -q`
- 必要に応じて fast-domain 側で `tests/unit_tests/test_logging.py` も実行する。

## 実装メモ

- `DateNamedDailyFileHandler` を追加し、当日の active file を `<base>_<YYYY-MM-DD>.log` として開く。
- emit 時に日付が変わった場合は stream を切り替える。
- `backup_count` を超えた古い日付ログを削除する。
- pytest の root logging capture handler は default handler 判定から除外し、アプリ側の root handler は尊重する。

## 検証

- `poetry run pytest tests/unit_tests/test_logging.py -q`: **9 passed**
- `poetry run pytest tests/unit_tests -q`: **831 passed, 10 skipped**
- fast-domain 側: `tests/unit_tests/test_logging.py tests/unit_tests/test_config_hook_standalone.py`: **16 passed**

## 関連コミット

- repom: `104b019 Fix dated logging handler`
- fast-domain: `4a3b0af Use repom dated logging handler`
- repom proposal: `docs/guide/tmp/fast_domain_logging_migration.md`（実装完了後に削除）
