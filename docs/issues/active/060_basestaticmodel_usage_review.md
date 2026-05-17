# Issue #60: `BaseStaticModel` の利用状況確認と deprecation/削除判断

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 低

## 問題の説明

`repom/models/base_static.py` で定義されている `BaseStaticModel` は repom 内部のいかなる場所からも利用されていない。

- 定義: [repom/models/base_static.py](../../../repom/models/base_static.py)
- 公開: [repom/models/__init__.py](../../../repom/models/__init__.py) の `__all__` に含まれる

grep の結果、ヒットは以下のみ:
- `repom/models/base_static.py`（自分自身）
- `repom/models/__init__.py`（export）
- `CLAUDE.md`, `AGENTS.md`（言及のみ）

ただし `__all__` に含まれているため、外部プロジェクト（`mine_py` など）が import して継承している可能性がある。直ちに削除はできない。

## 提案される解決策

2 段階で対応する:

1. **Phase 1（本 Issue）**: 利用調査
   - 既知の外部プロジェクト（`mine_py` 等、CLAUDE.md に登場するもの）で `BaseStaticModel` を継承しているか確認
   - 利用ゼロを確認できれば → Phase 2 へ
   - 利用ありなら → ガイド整備（`docs/guides/model/`）して維持判断

2. **Phase 2**: 利用がなければ次のいずれか
   - **削除**: `__all__` から外し、ファイル削除、CHANGELOG に記載
   - **deprecation**: `DeprecationWarning` を `__init__` 等で出し、次メジャーで削除

## 影響範囲

- `repom/models/base_static.py`
- `repom/models/__init__.py`
- ドキュメント（`docs/guides/model/`、`CLAUDE.md`、`AGENTS.md`）

## 実装計画

1. Phase 1: 外部プロジェクトで grep して利用状況を調査し、結果を本 Issue に追記
2. 結果に応じて Phase 2 の方針（削除 / deprecate / 維持）を決定
3. 維持の場合は利用ガイドを `docs/guides/model/` に追加
4. 削除/deprecation の場合は対応 PR を作成

## テスト計画

- 既存テスト全件パス
- 外部プロジェクト（mine_py 等）のテストが壊れないか確認

## 関連リソース

- [repom/models/base_static.py](../../../repom/models/base_static.py)
- [repom/models/__init__.py](../../../repom/models/__init__.py)
