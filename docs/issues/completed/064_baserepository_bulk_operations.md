# Issue #64: `BaseRepository` への bulk insert/update/delete ヘルパ追加

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 中

## 問題の説明

`BaseRepository` / `AsyncBaseRepository` は単一レコード操作 API（`add`, `update`, `delete`）のみを提供しており、bulk 操作のヘルパが存在しない。

- [repom/repositories/base_repository.py](../../../repom/repositories/base_repository.py)
- [repom/repositories/async_base_repository.py](../../../repom/repositories/async_base_repository.py)

このため、大量データを扱う利用側では:

1. ループで `repo.add(obj)` を呼ぶ → 1 件ずつ INSERT 文が走り遅い
2. 直接 `session.bulk_insert_mappings()` / `session.execute(insert(...))` を書く → リポジトリパターンを迂回

のいずれかになる。後者はソフトデリート規約や `default_options` などリポジトリ側で保証している契約を素通りするリスクがある。

## 提案される解決策

`BaseRepository` / `AsyncBaseRepository` 双方に以下を追加:

- `bulk_insert(objects: Sequence[T]) -> list[T]`
  - 内部で `session.add_all()` または `bulk_save_objects` / `insert().values([...])` を選択
- `bulk_update(values: Sequence[dict], *, filter_by: dict | None = None) -> int`
  - `update().where(...).values(...)` ベース、影響行数を返す
- `bulk_delete(filter_by: dict | None = None, ids: Sequence | None = None) -> int`
  - ソフトデリート対応モデルでは SoftDeleteRepositoryMixin と整合させる

実装方針は Issue #018 の `default_options` 実装と同様に「両リポジトリで対称な API」を保つ。

注意点:
- ソフトデリートカラム持ちモデルに対する `bulk_delete` は SoftDeleteRepositoryMixin と挙動を揃える（既定では論理削除）
- 戻り値の規約（生成オブジェクトを返すか件数だけ返すか）は API ガイドラインに従う
- バルク操作は session の identity_map と整合性に注意（必要に応じ `expire_all()`）

## 影響範囲

- `repom/repositories/base_repository.py`
- `repom/repositories/async_base_repository.py`
- `repom/repositories/_soft_delete.py`（bulk_delete と論理削除の協調）
- `docs/guides/repository/base_repository_guide.md`（API ガイド追記）
- 新規テスト: `tests/unit_tests/repositories/`

## 実装計画

1. API 仕様を docs/ideas/ または本 Issue に簡易設計として書く
2. sync 版を実装し、ユニットテストで bulk_insert/update/delete を網羅
3. async 版を sync と対称に実装
4. SoftDeletableMixin との協調テスト
5. ガイド更新（`base_repository_guide.md`）

## テスト計画

- 100 件規模の bulk_insert の正常系
- bulk_update で複数レコードの値が更新される
- bulk_delete で対象だけ削除され、論理削除モデルでは `is_deleted` が立つ
- 空 sequence の境界ケース
- async/sync 両方
- パフォーマンス測定（参考値: ループ add との比較）

## 関連リソース

- 関連完了 Issue: #018（default_options）, #015（SoftDeleteMixin）
- [repom/repositories/_core.py](../../../repom/repositories/_core.py)
- [repom/repositories/_soft_delete.py](../../../repom/repositories/_soft_delete.py)

## Completion

**Status**: ✅ 完了
**Completed**: 2026-05-17

Implemented sync/async `bulk_insert()`, `bulk_update()`, and `bulk_delete()`. Soft-delete models use `deleted_at` updates for bulk deletes. Added unit tests and repository guide updates.
