# mine-py 向け order_by ガイド書き換え依頼書

## 目的

mine-py 側の `order_by` ガイドを、現在の repom 正式仕様に合わせて書き換える。

対象は「文言修正」ではなく、実装パターンの正本を repom 準拠へ統一すること。

---

## 背景

現状の mine-py ガイドは、過去の運用で導入した独自解釈が含まれており、
以下の点で repom の現行仕様とずれる箇所がある。

- 基盤資料のリンクが旧ファイル名（`order_by_migration_guide.md`）を参照している
- virtual column の説明が「独自分岐パース（split(':')）」中心になっている
- `parse_order_by()` / OpenAPI helper の現在仕様（`VirtualColumnError` / `virtual_order_columns`）を前提にしていない

repom 側では、以下が公式仕様として実装済み。

- `virtual_order_columns` の公式サポート
- `get_order_by_columns()` / `get_order_by_values()` への virtual 列反映
- `parse_order_by()` が virtual 列で `VirtualColumnError` を送出
- canonical form（`column:asc` / `column:desc`）必須

---

## 書き換え対象

- mine-py の `docs/guides/development/order_by_guide.md`

---

## 依頼内容（必須）

### 1. 基盤資料リンクを更新する

旧:

- `submod/fast-domain/submod/repom/docs/guides/repository/order_by_migration_guide.md`

新:

- `submod/fast-domain/submod/repom/docs/guides/repository/order_by_guide.md`

### 2. virtual_order_columns セクションを repom 正式仕様ベースに書き換える

必須で明記すること:

- `virtual_order_columns` は repom の公式属性である
- `virtual_order_columns` に含める列は `allowed_order_columns` にも含める必要がある
- `parse_order_by()` は virtual 列に対して `VirtualColumnError` を送出する
- virtual 列のソート式はカスタムリポジトリメソッド側で実装する
- `find()` に virtual 列を直接渡す用途は非対応

### 3. カスタム実装例を `VirtualColumnError` 捕捉パターンへ変更する

旧パターン（非推奨）:

- `order_by.split(':')` で独自パース
- `len(parts)` による暗黙デフォルト方向の補完

新パターン（推奨）:

- `self.parse_order_by()` をまず呼ぶ
- virtual 列のみ `except VirtualColumnError` で分岐
- canonical 前提で direction を扱う

### 4. OpenAPI の説明を repom helper 前提へ揃える

- `build_order_by_query_depends()` が `allowed_order_columns` + `virtual_order_columns` から enum 候補を生成することを明記
- 422 の説明は「enum に候補が無い or 不正値」の整理で記載する

### 5. 用語と責務を統一する

- 「repom が関与しない」表現を削除し、以下の責務分離で説明する
  - repom: 候補列挙・canonical validation・virtual 列検出
  - 利用側 repository: virtual 列の実クエリ式実装

---

## 推奨サンプル（差し替え用）

```python
from repom import BaseRepository, VirtualColumnError
from sqlalchemy import asc, desc, select
from sqlalchemy.sql import nulls_last

class AniVideoUserStatusRepository(BaseRepository[AniVideoUserStatusModel]):
    default_order_by = "updated_at:desc"

    allowed_order_columns = BaseRepository.allowed_order_columns + [
        "status", "rating"
    ]
    virtual_order_columns = ["rating"]

    def find_by_anime_with_filters(self, ..., order_by: str = "updated_at:desc"):
        stmt = (
            select(AniVideoUserStatusModel)
            .outerjoin(
                AniVideoReviewModel,
                ...,
            )
        )

        try:
            order_expr = self.parse_order_by(AniVideoUserStatusModel, order_by)
        except VirtualColumnError as e:
            direction = desc if e.direction == "desc" else asc
            if e.column_name == "rating":
                order_expr = nulls_last(direction(AniVideoReviewModel.rating))
            else:
                raise

        stmt = stmt.order_by(order_expr)
        return self.session.execute(stmt).scalars().all()
```

---

## 受け入れ条件

- [ ] 基盤資料リンクが `order_by_guide.md` を参照している
- [ ] `virtual_order_columns` の説明が repom 公式仕様と一致している
- [ ] サンプル実装が `VirtualColumnError` 捕捉パターンになっている
- [ ] `split(':')` ベースの独自パース例が削除されている
- [ ] `find()` への virtual 直接指定非対応が明記されている
- [ ] canonical form 必須（`column:asc` / `column:desc`）が明記されている

---

## 備考

この依頼は「mine-py 固有運用を残しつつ、repom 正本への整合を取る」ためのもの。
完全に repom ガイドへ寄せるのではなく、mine-py 特有のクエリ例は残してよい。
ただし、仕様説明の主語は repom 正式機能を優先すること。
