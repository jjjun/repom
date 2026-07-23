# Technical documentation

このディレクトリは、現行実装の設計判断、制約、調査履歴を保存します。使い方は
[guides](../guides/README.md) に置き、実装タスクは issuekit API で管理します。

## 現行実装の設計資料

- [get_response_schema の内部設計](get_response_schema_technical.md)
- [Alembic version_locations の制約](alembic_version_locations_limitation.md)
- [ロギング戦略](hybrid_package_logging_strategy.md)

## 調査・履歴資料

- [前方参照自動解決の調査](auto_forward_refs_resolution.md)
- [Docker manager 共通化の分析](docker_manager_code_reduction_analysis.md)
- [Docker manager 初期実装計画](docker_manager_phase1_implementation_guide.md)
- [AI コンテキスト管理の検討](ai_context_management.md)

履歴資料では、過去の `repom._` 配下やローカル issue ファイルへの記述が現行 API
ではない場合があります。現行コードを変更する際は、必ず `repom/` とテストを
優先してください。汎用 discovery、Docker、設定 hook の実装は `basekit` が
所有し、repom は SQLAlchemy とサービス固有の差分だけを所有します。

## 更新ルール

- 現行仕様と過去案を見出しまたは注記で区別する。
- 外部パッケージの API を再録せず、所有元と repom 固有の差分を示す。
- 関連 Issue はローカルパスではなく `repom#<id>` として記載する。
- 実装ファイルへのリンクはリポジトリ相対パスで検証する。
