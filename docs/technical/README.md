# Technical documentation

このディレクトリは、現行実装の設計判断、制約、調査履歴を保存します。使い方は
[guides](../guides/README.md) に置き、実装タスクは issuekit API で管理します。

## 現行実装の設計資料

- [Alembic version_locations の制約](alembic_version_locations_limitation.md)

## 所有範囲と履歴

現行コードを変更する際は、必ず `repom/` とテストを優先してください。汎用 discovery、
Docker、logging、設定 hook の実装は `basekit` が所有し、repom は SQLAlchemy と
サービス固有の差分だけを所有します。文書の更新規則は[更新ルール](../README.md#更新ルール)
を参照してください。

Docker manager と hybrid logging の履歴メモは commit `bd95303` から、AI context
management のメモは commit `04c9f68` から復元できます。
