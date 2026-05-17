# Issue #65: `CLAUDE.md` のビルド/パッケージマネージャ記述を実態（uv + hatchling）に更新

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 中

## 問題の説明

直近の変更により、パッケージマネージャ・ビルドシステムが移行済みなのに `CLAUDE.md` が古い記述のまま。

- 最新コミット: `6352497 chore: migrate build system from poetry to hatchling`
- 完了 Issue: [#058 Poetry → uv 移行](../completed/058_migrate_from_poetry_to_uv.md)

しかし [CLAUDE.md](../../../CLAUDE.md) には以下が残っている:

```
- **Package Manager**: Poetry
...
Always use `poetry run` prefix:

poetry run pytest tests/unit_tests
poetry run db_create
...
```

このため:
- 新しい作業者（人/AI）が `poetry run` を実行し失敗 → 混乱
- 各 Issue/PR で使うコマンド例の規範が崩れる
- リポジトリ規約と実態の乖離は次のリファクタを誘発しがち

## 提案される解決策

`CLAUDE.md` の以下セクションを更新:

1. **Technology Stack**: `Package Manager: Poetry` → `Package Manager: uv` / `Build Backend: hatchling`
2. **Commands**: すべての `poetry run` を `uv run` に置換
3. **Project Structure**: `pyproject.toml` の説明があれば PEP 621 ベース + hatchling に整合
4. **Alembic** セクション等のコマンド例も `uv run alembic ...` に統一

合わせて確認:
- `AGENTS.md` も同様の記述があれば一緒に更新
- `README.md`（あれば）
- `docs/guides/` 配下に poetry 例が残っていないか grep

## 影響範囲

- `CLAUDE.md`
- `AGENTS.md`（要確認）
- `docs/guides/`（要確認）
- ソースコード自体は変更なし

## 実装計画

1. `grep -ri "poetry run" CLAUDE.md AGENTS.md docs/` で残存箇所を洗い出す
2. `poetry run` を `uv run` に置換
3. Package Manager / Build Backend のセクションを最新（uv + hatchling）に書き換え
4. PR で差分確認

## テスト計画

- ドキュメント変更のみ。テストへの影響なし
- `grep -ri "poetry" CLAUDE.md AGENTS.md docs/` が「歴史的経緯の言及」以外でゼロ件になることを確認

## 関連リソース

- 完了 Issue: [#058 Poetry → uv 移行](../completed/058_migrate_from_poetry_to_uv.md)
- コミット: `6352497 chore: migrate build system from poetry to hatchling`
