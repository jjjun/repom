# Issue #018: Repository Default Eager Loading Options Support

## Status
- **Created**: 2025-12-27
- **Completed**: 2025-12-28
- **Priority**: Medium
- **Complexity**: Low

## Problem Description

現在、`AsyncBaseRepository` や `BaseRepository` を継承したリポジトリで eager loading を設定する場合、`find()` や `get_by_id()` メソッド全体をオーバーライドする必要があります。

```python
class AniVideoItemRepository(AsyncBaseRepository[AniVideoItemModel]):
    async def find(self, params=None, filters=None, **kwargs):
        # オーバーライド全体が必要
        if 'options' not in kwargs:
            kwargs['options'] = []
        kwargs['options'].append(selectinload(self.model.tags))
        kwargs['options'].append(selectinload(self.model.personal_tags))
        return await super().find(built_filters, **kwargs)
    
    async def get_by_id(self, id: int):
        # これもオーバーライドが必要
        return await super().get_by_id(id, options=[
            selectinload(self.model.tags),
            selectinload(self.model.personal_tags)
        ])
```

この方法は冗長で、保守性が低いです。

## Expected Behavior

コンストラクタで `default_options` を設定し、`BaseRepository` が自動的にそれを使用する：

```python
class AniVideoItemRepository(AsyncBaseRepository[AniVideoItemModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(AniVideoItemModel, session)
        # コンストラクタで設定するだけ
        self.default_options = [
            selectinload(self.model.tags),
            selectinload(self.model.personal_tags)
        ]

# 使用例
repo = AniVideoItemRepository(session)
items = await repo.find()  # 自動的に default_options が適用される
item = await repo.get_by_id(1)  # これも自動的に適用される
```

## Solution Approach

### 1. BaseRepository の修正

`repom/repositories/base_repository.py` と `repom/repositories/async_base_repository.py` を修正：

```python
class BaseRepository:
    def __init__(self, model, session):
        self.model = model
        self.session = session
        self.default_options = []  # デフォルトは空リスト
    
    def find(self, filters=None, options=None, **kwargs):
        # options が None の場合のみ default_options を使用
        if options is None:
            options = self.default_options
        # ... 残りの実装
```

### 2. オプションのマージロジック

呼び出し時に `options` を明示的に渡した場合の動作：

- `options=None` → `default_options` を使用
- `options=[]` → 空リスト（eager loading なし）
- `options=[...]` → 指定されたオプションを使用（default_options は無視）

### 3. 影響を受けるメソッド（SELECT系のみ）

**✅ 影響あり（options パラメータを持つメソッド）**:
- `find()` - 複数取得
- `get_all()` - 全件取得
- `get_by_id()` - ID による単一取得
- `get_by()` - 条件による単一取得
- `get_one()` - フィルタによる単一取得
- `paginate()` - ページネーション（内部で find を呼ぶ）

**❌ 影響なし（options を使わないメソッド）**:
- `create()` - 作成
- `update()` - 更新
- `delete()` - 削除
- `count()` - 件数取得
- `exists()` - 存在確認

## Performance Impact

### ✅ メリット: N+1 問題の解決

**Without eager loading（現状の問題）**:
```python
items = await repo.find()  # 1回のクエリ
for item in items:
    print(item.tags)        # 各アイテムごとに1回のクエリ
    print(item.personal_tags)  # 各アイテムごとに1回のクエリ
# 合計: 1 + N×2 = 201回のクエリ（N=100の場合）
```

**With eager loading（default_options 使用）**:
```python
items = await repo.find()  # 3回のクエリで完了
# 1. items を取得
# 2. tags を IN句で一括取得
# 3. personal_tags を IN句で一括取得
for item in items:
    print(item.tags)        # クエリなし（すでにロード済み）
    print(item.personal_tags)  # クエリなし
# 合計: 3回のクエリ（N=100でも同じ）
```

**結果**: 100件なら **201回 → 3回** に削減（約67倍高速化）

### ⚠️ デメリット: 不要な eager load

リレーションを使わない場合でも eager load が発生：

```python
# リレーションを使わない場合
items = await repo.find()  # tags, personal_tags も取得してしまう
for item in items:
    print(item.title)  # title しか使わないのに...
```

**回避策**:
```python
# 明示的に options=[] を渡せば eager load をスキップ
items = await repo.find(options=[])  # default_options は無視される
```

### 📊 推奨使用ケース

**Eager load すべき場合**:
- リレーションをよく使う（8割以上のケース）
- 複数件取得が多い
- N+1 問題を避けたい

**Eager load しない方が良い場合**:
- リレーションをほとんど使わない
- 1件のみ取得する場合が多い
- メモリが限られている

## Implementation Details

### 対象ファイル

1. `repom/repositories/base_repository.py`
2. `repom/repositories/async_base_repository.py`
3. `repom/base_repository.py` (deprecated だが互換性のため)

### テスト

- `tests/unit_tests/test_base_repository.py` に default_options のテストを追加
- `tests/unit_tests/test_async_base_repository.py` にも追加

## Usage Examples

### ケース1: 通常使用（eager load あり）

```python
class AniVideoItemRepository(AsyncBaseRepository[AniVideoItemModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(AniVideoItemModel, session)
        # リレーションをよく使うなら設定
        self.default_options = [
            selectinload(self.model.tags),
            selectinload(self.model.personal_tags)
        ]

# 使用例
repo = AniVideoItemRepository(session)
items = await repo.find()  # tags, personal_tags がロード済み
```

### ケース2: リレーション不要な場合（eager load なし）

```python
# 明示的に options=[] を渡して高速化
items = await repo.find(options=[])  # 高速、メモリ節約
```

### ケース3: 特定のリレーションのみ

```python
# default_options を上書き
item = await repo.get_by_id(1, options=[
    selectinload(AniVideoItemModel.tags)  # personal_tags は除外
])
```

### ケース4: default_options なしのリポジトリ

```python
class SimpleRepository(AsyncBaseRepository[SimpleModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(SimpleModel, session)
        # default_options を設定しない（デフォルトは空リスト）

# 使用例
repo = SimpleRepository(session)
items = await repo.find()  # eager load なし（従来通り）
```

## Benefits

- ✅ メソッドのオーバーライドが不要
- ✅ DRY: eager loading の設定を一箇所に集約
- ✅ N+1 問題を簡単に解決（最大67倍高速化）
- ✅ 明示的な options 指定で上書き可能
- ✅ 既存コードに影響なし（後方互換性あり）
- ✅ SELECT 系メソッドにのみ影響（書き込み系は無関係）

## Related Documents

- [docs/guides/repository/README.md](../guides/repository/README.md)
- External project example: mine-py の AniVideoItemRepository
