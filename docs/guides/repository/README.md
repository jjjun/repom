# Repository ガイド一覧

同期・非同期 Repository API、検索条件の組み立て、並び順、トランザクション管理に
ついて説明します。

同期版と非同期版の公開 API の対応関係は
[`test_repository_api_parity.py`](../../../tests/unit_tests/test_repository_api_parity.py) で
検証されています。`BaseRepository` のガイドに記載した API は、特に説明がない限り
`AsyncBaseRepository` でも利用できます。

## ガイド

- [BaseRepository 基礎](base_repository_guide.md)
- [AsyncBaseRepository](async_repository_guide.md)
- [検索とフィルタ](repository_advanced_guide.md)
- [order_by](order_by_guide.md)
- [FilterParams](repository_filter_params_guide.md)
- [セッションとトランザクション管理](repository_session_patterns.md)

## 関連ガイド

- [Soft Delete](../model/soft_delete_guide.md)

アプリケーション側の Repository は、ドメインモデルを指定して
`BaseRepository` または `AsyncBaseRepository` を継承してください。
アプリケーション固有の検索処理は利用側プロジェクトに定義します。
