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

## Handoff protocol

Follow [AGENTS.md](AGENTS.md) and run `issuekit protocol --agent claude` or
`issuekit protocol --role <role>` for the current steps. Issuekit is the source
of truth for issue lifecycle and handoff instructions.
