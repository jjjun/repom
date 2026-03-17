# Issue #007: Annotation Inheritance の実装検証

## ステータス
- **段階**: 提案中（調査反映済み）
- **優先度**: 中
- **複雑度**: 中
- **作成日**: 2025-11-15
- **更新日**: 2026-03-17
- **関連 Issue**: #006 (SQLAlchemy 2.0 migration)

## 調査サマリ

- 現行実装は動作しており、重大な回帰は確認されていない。
- `BaseModel` の `__annotations__` 初期化は、`hasattr` ではなく `cls.__dict__` 判定に修正済み。
- 関連ユニットテスト（`test_base_model_auto.py` / `test_base_model_uuid.py`）は通過。
- ただし、Issue の主題である「annotation 継承と mixin 境界」の直接検証テストが不足している。

## 現在の実装（確認済み）

- 実装箇所: `repom/models/base_model.py`
  - `if '__annotations__' not in cls.__dict__: cls.__annotations__ = {}`
  - `id` / `created_at` / `updated_at` を動的追加時に `cls.__annotations__` へ反映

## 問題点（今回の調査で判明）

1. **Issue 文書の前提が一部古い**
- 「親 `__annotations__` 継承が常に原因」という断定は、Python 最新ドキュメントの注意事項（annotations の遅延評価・参照時挙動）に対して説明が粗い。

2. **将来互換の観点が未整理**
- Python 3.14 系の annotations 仕様（遅延評価・annotationlib 推奨）に対して、`__annotations__` 直接操作の方針を明示できていない。

3. **テストのギャップ**
- 既存テストは機能レベル（`use_id=False` で id が出ない等）は強いが、
  「mixin 継承時に `__annotations__` が想定通り保たれるか」の専用テストがない。

## 外部情報との整合メモ

- Python docs: class annotations は直接アクセス時に注意が必要（最新 docs では annotationlib/get_type_hints 系の利用が推奨寄り）。
- `typing.get_type_hints()` は class で MRO を辿り、注釈をマージする。
- SQLAlchemy 2.0 docs: `Mapped` / `mapped_column` と mixin 構成は公式サポート。

## 最小テスト案（今回実施対象）

追加先: `tests/unit_tests/test_annotation_inheritance.py`（新規）

### 1) 子クラス独立 annotations の確認
- **test_class_annotations_are_not_leaked_from_base_when_no_local_annotations**
- 目的: 子クラス作成時に、親クラス由来の不要 annotation を誤って採用しないことを確認。

### 2) Mixin annotation の維持確認
- **test_mixin_mapped_annotations_remain_visible_with_use_id_false**
- 目的: `TimestampMixin` などの `Mapped[...]` annotation が、`BaseModel` の初期化処理で消失しないことを確認。

### 3) 多重継承 + フラグ併用の確認
- **test_multiple_inheritance_with_use_flags_does_not_add_unexpected_id**
- 目的: `use_id=False` / `use_created_at=True` などの組み合わせで、想定外の `id` 追加が起きないことを確認。

### 4) 既存挙動のガード
- **test_existing_behavior_use_id_false_still_works_with_new_annotation_tests**
- 目的: 既存仕様（`use_id=False` モデルの主キー定義）が崩れていないことを、Issue 007 専用テスト内でも再確認。

## 実施スコープ（最小）

- ドキュメント更新: この Issue ファイルのみ
- テスト追加: 上記 4 ケース（ユニットのみ）
- 実装変更: **なし**（まずは回帰テストを先に追加）

## 完了条件

- [x] 調査結果を Issue 文書へ反映
- [x] `test_annotation_inheritance.py` を追加
- [x] 上記 4 テストが通過
- [ ] 必要なら実装修正を別 Issue へ分離（最小変更原則）

## 関連ファイル

- `repom/models/base_model.py`
- `tests/unit_tests/test_model_no_id.py`
- `tests/unit_tests/test_base_model_auto.py`
- `tests/unit_tests/test_base_model_uuid.py`

## 参考資料

- Python Data Model: `__annotations__`
  - https://docs.python.org/3/reference/datamodel.html#object.__annotations__
- Python typing: `get_type_hints`
  - https://docs.python.org/3/library/typing.html#typing.get_type_hints
- PEP 526
  - https://peps.python.org/pep-0526/
- SQLAlchemy 2.0 Declarative Tables
  - https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
- SQLAlchemy 2.0 Declarative Mixins
  - https://docs.sqlalchemy.org/en/20/orm/declarative_mixins.html
