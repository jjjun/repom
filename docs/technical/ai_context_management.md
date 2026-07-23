# AI context management

この資料は、過去に複数の AI 向け指示ファイルへ同じプロジェクト仕様を複製していた
問題を整理した記録です。現行方針は「正本を1つにし、用途別資料からリンクする」です。

## 現行の正本

| 内容 | 正本 |
| --- | --- |
| 開発規約、コマンド、handoff | [`AGENTS.md`](../../AGENTS.md) |
| 導入、公開 API、設定概要 | [`README.md`](../../README.md) |
| Issue lifecycle | `issuekit protocol --role <role>` |
| console scripts | `pyproject.toml` の `[project.scripts]` |
| pytest 設定 | `pyproject.toml` の `[tool.pytest.ini_options]` |
| 機能の使い方 | [guides](../guides/README.md) |
| 設計判断と制約 | [technical](README.md) |

`CLAUDE.md` と `.github/copilot-instructions.md` は tool 固有の短い入口だけを持ち、
プロジェクト仕様を再録しません。

## 更新原則

1. 実装とテストを先に確認し、現行仕様を guide に反映する。
2. 同じ説明が必要な場合は正本へリンクする。
3. 過去案は technical に残せるが、「現行」「履歴」を明記する。
4. Issue と cross-project proposal は issuekit API に置き、ローカル tracker を作らない。
5. 外部 package が所有する API は、その package の正本へ委ね、repom 固有の差分だけを
   説明する。

この方針により、長い AI prompt の同期漏れと、廃止済み path / command の再利用を
防ぎます。
