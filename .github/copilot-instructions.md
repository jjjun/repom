# GitHub Copilot instructions for repom

[AGENTS.md](../AGENTS.md) が、このリポジトリのプロジェクト規約と作業手順の正本です。
提案・編集の前に必ず参照してください。このファイルでは同じ仕様を複製しません。

補足:

- Python 3.12 以上、SQLAlchemy 2.x、`uv` を使用する。
- import は公開 API を優先する:
  `from repom import BaseModel, BaseModelAuto, BaseRepository, AsyncBaseRepository`
- DB セッション API は `repom.database`、テスト fixture helper は
  `repom.testing` から import する。
- アプリ固有のモデルや Repository は利用側プロジェクトに置く。
- テストは `uv run pytest`、詳細ログが必要な場合は `uv run pytest -vv -s`。
- Issue と提案の手順は `issuekit protocol --role <role>` を正本とする。

機能別の入口は [docs/guides/README.md](../docs/guides/README.md)、設計判断は
[docs/technical/README.md](../docs/technical/README.md) を参照してください。
