# Issue #052: virtual_order_columns — JOIN 先・集計列のソート公式サポート

**ステータス**: ✅ 完了

**作成日**: 2026-03-17

**優先度**: 中

---

## 問題の説明

`repom` の `get_order_by_columns()` と `parse_order_by()` は実カラム（SQLAlchemy mapper に登録されたカラム）しか扱えない。そのため JOIN 先テーブルのカラムや集計値など、「モデルに実カラムが存在しない列でのソート」が必要な場面で以下の挙動になる。

**`get_order_by_columns()`**（`_order_by.py`）:

```python
model_columns = set(mapper.columns.keys())
return [column for column in allowed_columns if column in model_columns]
# → virtual 列は mapper に存在しないため除外される
```

→ `build_order_by_query_depends()` が生成する OpenAPI enum に virtual 列が含まれない。

**`parse_order_by()`**（`_core.py`）:

```python
if not hasattr(model_class, column_name):
    raise ValueError(f"Column '{column_name}' does not exist on model")
```

→ virtual 列を渡すと `ValueError` になる（カスタムリポジトリメソッドからも呼べない）。

### 現在の回避策（mine-py）

mine-py 側で `virtual_order_columns = ["rating"]` というクラス属性を独自定義し、
カスタムクエリメソッド内でパース・ソートを手書きしている。
しかし **repom はこの属性を一切認識しない**ので、ドキュメントとコードが乖離している。

---

## 期待する動作

```python
class AniVideoUserStatusRepository(BaseRepository[AniVideoUserStatusModel]):
    default_order_by = "updated_at:desc"

    allowed_order_columns = BaseRepository.allowed_order_columns + ["status", "rating"]
    virtual_order_columns = ["rating"]  # ← repom が認識する公式属性
```

1. `get_order_by_columns()` が `rating` を結果に含める
2. `build_order_by_query_depends()` が `rating:asc` / `rating:desc` を OpenAPI enum に含める
3. `parse_order_by()` が virtual 列を受け取ったとき、専用例外 `VirtualColumnError` を送出する
4. カスタムリポジトリメソッドは `VirtualColumnError` を捕捉して自前ソートを適用する

---

## 影響範囲

| ファイル | 変更内容 |
|----------|----------|
| `repom/repositories/_order_by.py` | `get_order_by_columns()` に virtual 列バイパスを追加 |
| `repom/repositories/_core.py` | `parse_order_by()` に virtual 列チェックと `VirtualColumnError` 送出を追加 |
| `repom/repositories/_query_builder.py` | `QueryBuilderMixin.virtual_order_columns` クラス属性を追加 |
| `repom/repositories/__init__.py` | `VirtualColumnError` をエクスポート |
| `repom/__init__.py` | `VirtualColumnError` をエクスポート |
| `tests/unit_tests/repositories/` | 新規テスト追加 |
| `docs/guides/repository/order_by_guide.md` | virtual_order_columns セクション追加 |

---

## 実装計画

### Step 1: `VirtualColumnError` の定義

`_order_by.py` に専用例外を追加する。

```python
class VirtualColumnError(Exception):
    """Raised when parse_order_by encounters a virtual column.
    
    The caller (custom repository method) is responsible for
    applying the sort logic for this column.
    """
    def __init__(self, column_name: str, direction: str):
        self.column_name = column_name
        self.direction = direction
        super().__init__(
            f"'{column_name}' is a virtual column. "
            "Handle sort manually in the repository method."
        )
```

### Step 2: `QueryBuilderMixin` にクラス属性追加

`_query_builder.py`:

```python
class QueryBuilderMixin(Generic[T]):
    allowed_order_columns = ['id', 'title', 'created_at', 'updated_at', ...]
    virtual_order_columns: list[str] = []   # ← 追加
    default_order_by = None
```

### Step 3: `get_order_by_columns()` の修正

`_order_by.py`:

```python
def get_order_by_columns(repository_class: type) -> list[str]:
    model_class = get_repository_model_class(repository_class)
    allowed_columns = list(getattr(repository_class, "allowed_order_columns", []))
    virtual_columns = set(getattr(repository_class, "virtual_order_columns", []))

    mapper = sa_inspect(model_class)
    model_columns = set(mapper.columns.keys())

    return [
        column for column in allowed_columns
        if column in model_columns or column in virtual_columns  # ← virtual は通過
    ]
```

### Step 4: `parse_order_by()` の修正

`_core.py`:

```python
def parse_order_by(model_class, order_by_str: str, allowed_order_columns: List[str],
                   virtual_order_columns: List[str] | None = None):
    column_name, direction = normalize_order_by_value(order_by_str)

    if column_name not in allowed_order_columns:
        raise ValueError(f"Column '{column_name}' is not allowed for sorting")

    if direction not in ['asc', 'desc']:
        raise ValueError(f"Direction must be 'asc' or 'desc', got '{direction}'")

    # virtual 列は hasattr チェックをスキップして専用例外を送出
    if virtual_order_columns and column_name in virtual_order_columns:
        raise VirtualColumnError(column_name, direction)

    if not hasattr(model_class, column_name):
        raise ValueError(f"Column '{column_name}' does not exist on model")

    column = getattr(model_class, column_name)
    return desc(column) if direction == 'desc' else asc(column)
```

`QueryBuilderMixin.parse_order_by()` も `virtual_order_columns` を渡すよう修正する。

### Step 5: カスタムリポジトリの利用パターン

```python
from repom.repositories import VirtualColumnError
from sqlalchemy import asc, desc
from sqlalchemy.sql import nulls_last

def find_with_rating(self, order_by: str = "updated_at:desc"):
    stmt = select(MyModel).outerjoin(ReviewModel, ...)

    try:
        order_expr = self.parse_order_by(MyModel, order_by)
    except VirtualColumnError as e:
        direction = desc if e.direction == "desc" else asc
        if e.column_name == "rating":
            order_expr = nulls_last(direction(ReviewModel.rating))
        else:
            order_expr = direction(MyModel.updated_at)  # fallback

    return self.session.execute(stmt.order_by(order_expr)).scalars().all()
```

---

## 設計上の判断事項

### virtual 列を `find()` / `set_find_option()` に通した場合の挙動

`find()` は汎用メソッドであり、virtual 列のソートロジックを知らない。
そのため `VirtualColumnError` はキャッチせず、そのまま伝播させる。

**方針**: virtual 列を `find()` に渡すことは非対応・ドキュメントで明记する。
virtual 列のソートが必要な場合は専用のカスタムクエリメソッドを実装する。

### `default_order_by` に virtual 列を指定した場合

`get_order_by_default_value()` は virtual 列を `get_order_by_values()` 経由で検証するため、
virtual 列を `default_order_by` に指定してもバリデーションを通過する。
ただし `find()` で使われると `VirtualColumnError` が伝播するため、
**virtual 列を `default_order_by` に設定することは非推奨**とドキュメントに明記する。

---

## テスト計画

- `get_order_by_columns()`: virtual 列が結果に含まれること
- `get_order_by_values()`: virtual 列の `column:asc` / `column:desc` が含まれること
- `parse_order_by()`: virtual 列で `VirtualColumnError` が送出されること
- `VirtualColumnError`: `column_name` / `direction` 属性が正しいこと
- `build_order_by_query_depends()`: virtual 列が OpenAPI enum に含まれること
- virtual 列を `allowed_order_columns` に含めず `virtual_order_columns` のみに含めた場合のエラー

---

## 関連

- Issue #051: `order_by` OpenAPI introspection（本 Issue の前提）
- mine-py: `docs/guides/development/order_by_guide.md`（実運用での課題起点）

---

## 実装結果（2026-03-17）

- `QueryBuilderMixin.virtual_order_columns` を公式クラス属性として追加
- `get_order_by_columns()` が virtual 列を OpenAPI 候補に含めるよう修正
- `virtual_order_columns` が `allowed_order_columns` に含まれない場合は `ValueError` を送出
- `parse_order_by()` が virtual 列で `VirtualColumnError` を送出するよう修正
- `VirtualColumnError` を `repom.repositories` / `repom` から公開
- `order_by` 移行ガイドに virtual 列の運用ルールを追記

## テスト結果（2026-03-17）

- `tests/unit_tests/test_order_by_openapi.py`: 16 passed
- `tests/unit_tests/test_repository_default_order_by.py`: 10 passed
- `tests/unit_tests/test_async_repository_default_order_by.py`: 10 passed
- `tests/unit_tests/test_query_builder_defaults.py`: 5 passed
