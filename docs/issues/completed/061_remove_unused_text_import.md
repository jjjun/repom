# Issue #61: `repom/scripts/repom_info.py` の未使用 import (`text`) 除去

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 低

## 問題の説明

[repom/scripts/repom_info.py:8](../../../repom/scripts/repom_info.py#L8) で `from sqlalchemy import text, create_engine` と書かれているが、`text` はファイル内で一度も使われていない。

```python
from sqlalchemy import text, create_engine  # ← text は未使用
```

リンタが警告を出していない場合、設定見直しも合わせて検討する余地がある。

## 提案される解決策

- import 行から `text` を削除し、`from sqlalchemy import create_engine` に置き換える
- 他のスクリプトファイルにも同様の未使用 import がないか軽く確認する（`ruff check --select F401` 等）

## 影響範囲

- [repom/scripts/repom_info.py](../../../repom/scripts/repom_info.py)
- （副次）プロジェクト全体の未使用 import 洗い出し

## 実装計画

1. `repom_info.py` の `text` import を除去
2. `uv run ruff check --select F401 repom/` などで他に未使用 import がないか確認
3. 見つかれば同 Issue 内で同時除去（小さい範囲のため）

## テスト計画

- `uv run pytest` で回帰なし
- `uv run repom_info` で CLI 正常動作

## 関連リソース

- [repom/scripts/repom_info.py:8](../../../repom/scripts/repom_info.py#L8)

## 完了メモ

- 現在の `repom/scripts/repom_info.py` では `text` は `test_postgres_connection()` 内の `conn.execute(text("SELECT 1"))` で使用されている。
- `ruff check --select F401` はこの環境に ruff が入っていないため実行不可だったが、対象 import は未使用ではないことをコード上で確認。
- 変更不要として完了。
