# セッション管理ガイド

repom は、SQLAlchemy セッションの管理を簡素化するためのヘルパー関数を提供しています。
このガイドでは、`repom.database` モジュールの使い方を説明します。

## 📚 目次

1. [概要](#概要)
2. [提供される関数](#提供される関数)
3. [使用例](#使用例)
   - [FastAPI での使用](#fastapi-での使用)
   - [CLI スクリプトでの使用](#cli-スクリプトでの使用)
   - [Flask での使用](#flask-での使用)
   - [明示的なセッション管理](#明示的なセッション管理)
4. [設計原則](#設計原則)
5. [トラブルシューティング](#トラブルシューティング)

---

## 概要

`repom.database` モジュールは、フレームワーク非依存な設計で、様々な環境で使用できる汎用的なセッション管理機能を提供します。

**主な特徴**:
- ✅ フレームワーク非依存（FastAPI、Flask、Django、CLI など）
- ✅ トランザクション管理の自動化
- ✅ セッションのライフサイクル管理
- ✅ シンプルで直感的な API

---

## 提供される関数

### 1. `get_db_session()`

トランザクション管理なしのセッションを提供するジェネレータ関数です。

```python
def get_db_session() -> Generator[Session, None, None]:
    """
    トランザクションなしのセッションを提供します。
    
    - 明示的に commit() を呼ぶ必要があります
    - FastAPI の Depends() で使用可能
    - 自動的にセッションをクローズします
    """
```

**使い所**:
- 読み取り専用の操作
- トランザクション管理を自分で制御したい場合

---

### 2. `get_db_transaction()`

トランザクション管理付きのセッションを提供するジェネレータ関数です。

```python
def get_db_transaction() -> Generator[Session, None, None]:
    """
    トランザクション管理付きのセッションを提供します。
    
    - 正常終了時に自動コミット
    - 例外発生時に自動ロールバック
    - FastAPI の Depends() で使用可能
    - 自動的にセッションをクローズします
    """
```

**使い所**:
- データの作成、更新、削除
- トランザクションを自動管理したい場合

---

### 3. `transaction()`

トランザクション管理用のコンテキストマネージャーです。

```python
@contextmanager
def transaction() -> Generator[Session, None, None]:
    """
    トランザクション管理用のコンテキストマネージャー。
    
    - with 文で使用
    - 正常終了時に自動コミット
    - 例外発生時に自動ロールバック
    - CLI スクリプトや通常の Python コードで使用
    """
```

**使い所**:
- CLI スクリプト
- バッチ処理
- 通常の Python コード（非 Web フレームワーク）

---

### 4. `get_session()`

新しいセッションインスタンスを直接取得します。

```python
def get_session() -> Session:
    """
    新しいセッションインスタンスを直接取得します。
    
    - トランザクション管理は手動
    - セッションのクローズも手動
    - 低レベルな制御が必要な場合に使用
    """
```

**使い所**:
- 低レベルな制御が必要な場合
- 特殊なトランザクション管理が必要な場合

---

## 使用例

### FastAPI での使用

#### パターン 1: 読み取り専用の操作

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from repom.database import get_db_session

router = APIRouter()

@router.get("/items")
async def read_items(session: Session = Depends(get_db_session)):
    """アイテム一覧を取得"""
    items = session.query(Item).all()
    return items

@router.get("/items/{item_id}")
async def read_item(
    item_id: int,
    session: Session = Depends(get_db_session)
):
    """特定のアイテムを取得"""
    item = session.query(Item).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

#### パターン 2: データの作成・更新・削除

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from repom.database import get_db_transaction

router = APIRouter()

@router.post("/items")
async def create_item(
    item_data: ItemCreate,
    session: Session = Depends(get_db_transaction)
):
    """新しいアイテムを作成（自動コミット）"""
    item = Item(**item_data.dict())
    session.add(item)
    # トランザクションは自動的にコミットされます
    return item

@router.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item_data: ItemUpdate,
    session: Session = Depends(get_db_transaction)
):
    """アイテムを更新（自動コミット）"""
    item = session.query(Item).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    for key, value in item_data.dict(exclude_unset=True).items():
        setattr(item, key, value)
    
    # トランザクションは自動的にコミットされます
    return item

@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    session: Session = Depends(get_db_transaction)
):
    """アイテムを削除（自動コミット）"""
    item = session.query(Item).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    session.delete(item)
    # トランザクションは自動的にコミットされます
    return {"message": "Item deleted successfully"}
```

#### パターン 3: 複数の操作をまとめて実行

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from repom.database import get_db_transaction

router = APIRouter()

@router.post("/blocks/bulk")
async def create_bulk_blocks(
    blocks_data: List[BlockCreate],
    session: Session = Depends(get_db_transaction)
):
    """150個のブロックを一括保存（自動コミット）"""
    blocks = []
    for block_data in blocks_data:
        block = Block(**block_data.dict())
        session.add(block)
        blocks.append(block)
    
    # すべての操作が1つのトランザクションで実行されます
    # 途中で例外が発生した場合、すべての操作がロールバックされます
    return blocks
```

---

### CLI スクリプトでの使用

#### パターン 1: 単純なデータ操作

```python
from repom.database import transaction
from repom.models import Item

def create_initial_data():
    """初期データを作成"""
    with transaction() as session:
        # データを作成
        item1 = Item(name="Item 1", description="First item")
        item2 = Item(name="Item 2", description="Second item")
        
        session.add(item1)
        session.add(item2)
        
        # with ブロック終了時に自動コミット
        print("Initial data created successfully")

if __name__ == "__main__":
    create_initial_data()
```

#### パターン 2: バッチ処理

```python
from repom.database import transaction
from repom.models import Block

def process_blocks(block_ids: List[int]):
    """ブロックをバッチ処理"""
    with transaction() as session:
        # ブロックを取得
        blocks = session.query(Block).filter(Block.id.in_(block_ids)).all()
        
        # 処理
        for block in blocks:
            block.processed = True
            block.processed_at = datetime.utcnow()
        
        print(f"Processed {len(blocks)} blocks")
        # with ブロック終了時に自動コミット

if __name__ == "__main__":
    block_ids = [1, 2, 3, 4, 5]
    process_blocks(block_ids)
```

#### パターン 3: エラーハンドリング

```python
from repom.database import transaction
from repom.models import Item

def safe_create_item(name: str, description: str):
    """エラーハンドリング付きでアイテムを作成"""
    try:
        with transaction() as session:
            item = Item(name=name, description=description)
            session.add(item)
            print(f"Item '{name}' created successfully")
            return item
    except Exception as e:
        # エラー発生時は自動的にロールバック
        print(f"Error creating item: {e}")
        return None

if __name__ == "__main__":
    safe_create_item("Test Item", "This is a test")
```

---

### Flask での使用

```python
from flask import Flask, request, jsonify
from repom.database import get_db_transaction, get_db_session

app = Flask(__name__)

@app.route('/items', methods=['GET'])
def get_items():
    """アイテム一覧を取得"""
    gen = get_db_session()
    session = next(gen)
    try:
        items = session.query(Item).all()
        return jsonify([item.to_dict() for item in items])
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

@app.route('/items', methods=['POST'])
def create_item():
    """新しいアイテムを作成"""
    data = request.get_json()
    
    gen = get_db_transaction()
    session = next(gen)
    try:
        item = Item(**data)
        session.add(item)
        # 自動コミット
        return jsonify(item.to_dict()), 201
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
```

---

### 明示的なセッション管理

特殊なケースで低レベルな制御が必要な場合は、`get_session()` を使用します。

```python
from repom.database import get_session

def advanced_transaction():
    """複雑なトランザクション制御"""
    session = get_session()
    
    try:
        # セーブポイントを作成
        savepoint = session.begin_nested()
        
        # 最初の操作
        item1 = Item(name="Item 1")
        session.add(item1)
        
        # セーブポイントにロールバック
        savepoint.rollback()
        
        # 別の操作
        item2 = Item(name="Item 2")
        session.add(item2)
        
        # コミット
        session.commit()
        
    except Exception as e:
        # エラー時はロールバック
        session.rollback()
        raise
    finally:
        # 必ずクローズ
        session.close()
```

---

## 設計原則

### 1. フレームワーク非依存

`repom.database` のすべての関数は、特定のフレームワークに依存しない設計です。

- ❌ FastAPI 専用ではない
- ❌ Flask 専用ではない
- ✅ どのフレームワーク・環境でも使用可能

### 2. ジェネレータの汎用性

`get_db_session()` と `get_db_transaction()` は、FastAPI の `Depends()` だけでなく、
他のフレームワークでも使用できるジェネレータ関数です。

```python
# FastAPI
session: Session = Depends(get_db_transaction)

# Flask
gen = get_db_transaction()
session = next(gen)

# Django
gen = get_db_transaction()
session = next(gen)
```

### 3. SessionLocal の使用

各関数は `SessionLocal()` を呼び出して新しいセッションを生成します。
これにより、各リクエスト・トランザクションで独立したセッションが作成されます。

```python
# repom/database.py
from repom.db import SessionLocal

def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()  # 新しいセッション
    try:
        yield session
    finally:
        session.close()
```

### 4. シンプルな責任分離

- `db.py`: データベースエンジンと基本設定
- `session.py`: セッション管理（本モジュール）
- `base_repository.py`: データアクセス層

---

## トラブルシューティング

### Q1: `get_db_transaction()` を使っているのにコミットされない

**原因**: ジェネレータが正しく終了していない可能性があります。

**解決策**:
```python
# ❌ 間違った使い方
gen = get_db_transaction()
session = next(gen)
session.add(item)
# ジェネレータが終了していない → コミットされない

# ✅ 正しい使い方（FastAPI）
@router.post("/items")
async def create_item(session: Session = Depends(get_db_transaction)):
    session.add(item)
    # FastAPI が自動的にジェネレータを終了 → コミットされる

# ✅ 正しい使い方（手動）
gen = get_db_transaction()
session = next(gen)
try:
    session.add(item)
finally:
    try:
        next(gen)  # ジェネレータを終了
    except StopIteration:
        pass
```

---

### Q2: セッションがクローズされていないようだ

**原因**: `get_session()` を使用している場合、手動でクローズする必要があります。

**解決策**:
```python
# ❌ 間違った使い方
session = get_session()
session.add(item)
session.commit()
# クローズしていない → リソースリーク

# ✅ 正しい使い方
session = get_session()
try:
    session.add(item)
    session.commit()
finally:
    session.close()  # 必ずクローズ
```

---

### Q3: FastAPI で `Depends()` が機能しない

**原因**: 関数のシグネチャが正しくない可能性があります。

**解決策**:
```python
# ❌ 間違った使い方
@router.post("/items")
async def create_item(session = Depends(get_db_transaction)):
    # 型ヒントがない

# ✅ 正しい使い方
@router.post("/items")
async def create_item(session: Session = Depends(get_db_transaction)):
    # 型ヒントを追加
```

---

### Q4: トランザクションが意図せずロールバックされる

**原因**: 例外が発生している可能性があります。

**解決策**:
```python
# デバッグ用のログを追加
from repom.database import transaction

try:
    with transaction() as session:
        item = Item(name="test")
        session.add(item)
        # ここで例外が発生していないか確認
        print(f"Item added: {item}")
except Exception as e:
    # 例外の内容を確認
    print(f"Transaction failed: {e}")
    raise
```

---

### Q5: 複数のトランザクションが干渉している

**原因**: `db_session` (scoped_session) と `SessionLocal` を混同している可能性があります。

**解決策**:
```python
# ❌ 間違った使い方
from repom.db import db_session  # scoped_session（スレッドローカル）
from repom.database import get_db_transaction  # SessionLocal（独立）

# これらを混ぜると予期しない動作になる

# ✅ 正しい使い方
from repom.database import get_db_transaction, transaction

# repom.database のみを使用する
```

---

## まとめ

`repom.database` モジュールは、シンプルで汎用的なセッション管理機能を提供します。

**使い分けガイド**:

| 関数 | 使い所 | トランザクション管理 |
|------|--------|---------------------|
| `get_db_session()` | 読み取り専用、FastAPI | 手動 |
| `get_db_transaction()` | 書き込み操作、FastAPI | 自動 |
| `transaction()` | CLI、バッチ処理 | 自動 |
| `get_session()` | 低レベル制御 | 手動 |

**推奨事項**:
- ✅ 基本的には `get_db_transaction()` または `transaction()` を使用
- ✅ 読み取り専用の場合は `get_db_session()` を使用
- ⚠️ `get_session()` は特殊なケースのみ使用
