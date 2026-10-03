# CLAUDE.md - repom

このリポジトリで作業する前に [AGENTS.md](AGENTS.md) を読み、その指示を正本として
使用してください。プロジェクト構造、テスト、設定、Issue 管理、handoff の手順を
このファイルには複製しません。

Claude 固有の補足:

- コマンドはリポジトリルートから `uv run ...` で実行する。
- 実装前に関連する [ガイド一覧](docs/guides/README.md) と
  [技術資料一覧](docs/technical/README.md) を確認する。
- Issue の手順は `issuekit protocol --agent claude` または
  `issuekit protocol --role <role>` を実行して確認する。
- アプリ固有のモデル・Repository・API をこの共有パッケージへ追加しない。

## Security review

セキュリティレビューと関連変更では [SECURITY.md](SECURITY.md) と、対象パスに
適用される入れ子の `SECURITY.md` を読み、[AGENTS.md](AGENTS.md) の
Security Review Context に従ってください。Codex 専用プラグインがなくても、
この共通ポリシーをソースと照合してレビューできます。

確認観点と結果の記録形式には [共通チェックリストのひな形](docs/guides/security/security_review_checklist.md)
があります。現在は暫定版（試行運用中）です。ポリシーの代替や監査済みの証明として扱わず、
使って分かった過不足は結果の「チェックリストへのフィードバック」に記録してください。

`SECURITY.md` 自体のチェックを依頼された場合:

1. 各節の前提・制御・既定値を実装、関連テスト、公開ガイドと照合する。
   テストの存在と実行による検証を区別する。
2. 利用側アプリの責任と repom の保証を区別し、同期・非同期、SQLite・PostgreSQL、
   CLI・Python API で保証を広げすぎていないか確認する。
3. 監査対象の抜け、根拠のない除外・リスク受容、未確認の運用前提を確認する。
4. 指摘にはポリシーの節、根拠となるソース位置、監査への影響、修正文案を付ける。
   文書の不整合・改善提案・検証済みの脆弱性を区別し、未確認範囲も報告する。

レビューだけの依頼では結果を報告し、修正や監査の実行は依頼された範囲に従う。
機密情報や詳細な再現手順をこの指示ファイルや共通ポリシーへ転載しない。

## Handoff protocol

Follow [AGENTS.md](AGENTS.md) and run `issuekit protocol --agent claude` or
`issuekit protocol --role <role>` for the current steps. Issuekit is the source
of truth for issue lifecycle and handoff instructions.
