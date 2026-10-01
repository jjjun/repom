# repom documentation

repom の資料は用途別に次の3種類へ分けています。

| ディレクトリ | 内容 | 状態 |
| --- | --- | --- |
| [guides/](guides/README.md) | 現行機能の使い方 | 実装変更に合わせて更新 |
| [technical/](technical/README.md) | 設計判断、制約、過去の調査 | 履歴資料はその旨を明記 |
| [ideas/](ideas/README.md) | 未実装の機能アイデア | 実装済み機能と混同しない |

プロジェクトの導入と公開 API はルートの [README](../README.md)、開発規約は
[AGENTS.md](../AGENTS.md) が正本です。

## 情報の正本

| 内容 | 正本 |
| --- | --- |
| 開発規約、コマンド、handoff | [AGENTS.md](../AGENTS.md) |
| 導入、公開 API、設定概要 | [README.md](../README.md) |
| Issue lifecycle | `issuekit protocol --role <role>` |
| console scripts | `pyproject.toml` の `[project.scripts]` |
| pytest 設定 | `pyproject.toml` の `[tool.pytest.ini_options]` |
| 機能の使い方 | [guides](guides/README.md) |
| 設計判断と制約 | [technical](technical/README.md) |

`CLAUDE.md` と `.github/copilot-instructions.md` は tool 固有の短い入口だけを持ち、
プロジェクト仕様を再録しません。

## Issue とクロスプロジェクト提案

Issue は issuekit API の `project = "repom"` で管理します。廃止済みの
`docs/issue` / `docs/issues` トラッカーを作り直さないでください。手順は
`issuekit protocol --role <role>` または MCP の `get_protocol` で確認します。

`docs/issues/` には案内用の README のみを置きます。ローカルの Issue ファイルや
索引は追加しないでください。

repom 外の変更が必要な場合は `issuekit propose --to <project>` を使用します。
ローカルの `docs/proposals` は使用しません。

## 更新ルール

- guides は現行の import path、CLI、設定名、戻り値を実装とテストで確認する。
- technical の履歴資料は、現行仕様と過去案を明確に区別する。
- ideas のコードは未実装の概念例であることを明記する。
- 同じ仕様を複数ファイルへコピーせず、正本へリンクする。
- 外部 package が所有する API はその正本へ委ね、repom 固有の差分だけを記載する。
- リポジトリ内リンクは相対パスを使い、端末固有の絶対パスを記載しない。
