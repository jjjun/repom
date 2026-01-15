# 外部セッション commit 動作変更 - 移行ガイド

**対象バージョン**: repom v2.x.x 以降

**変更内容**: Repository が外部セッションを受け取った場合、`save()` / `saves()` / `remove()` は `flush()` のみを実行し、`commit()` を実行しなくなりました。

---

## 📋 影響チェックリスト

以下のいずれかに該当する場合、コードの確認・修正が必要な可能性があります：

### ✅ 確認が必要なケース

- [ ] **FastAPI Depends パターンで Repository を使用している**
  ```python
  @router.post("/items")
  def create_item(session: Session = Depends(get_db_session)):
      repo = ItemRepository(session)
      item = repo.save(Item(name="test"))
      # ← commit が必要
  ```

- [ ] **with 文でトランザクションを管理している**
  ```python
  with _db_manager.get_sync_transaction() as session:
      repo = ItemRepository(session)
      item = repo.save(Item(name="test"))
      # ← commit は with 終了時に自動実行（問題なし）
  ```

- [ ] **save() 直後に created_at/updated_at を参照している**
  ```python
  item = repo.save(Item(name="test"))
  print(item.created_at)  # ← None の可能性
  ```

### ⭕ 影響がないケース

- [ ] **内部セッション（session=None）を使用している**
  ```python
  repo = ItemRepository()  # session=None
  item = repo.save(Item(name="test"))  # 自動 commit される
  ```

- [ ] **既に明示的に session.commit() を呼んでいる**
  ```python
  repo = ItemRepository(session)
  item = repo.save(Item(name="test"))
  session.commit()  # 元々書いていた場合は問題なし
  ```

---

## 🔍 影響分析

### 1. FastAPI Depends パターン（最も影響大）

**変更前の動作**:
```python
@router.post("/items")
def create_item(
    item_data: ItemCreate,
    session: Session = Depends(get_db_session)
):
    repo = ItemRepository(session)
    item = repo.save(Item(**item_data.dict()))
    # ← save() が自動 commit していた
    return item
```

**変更後の動作**:
```python
@router.post("/items")
def create_item(
    item_data: ItemCreate,
    session: Session = Depends(get_db_session)
):
    repo = ItemRepository(session)
    item = repo.save(Item(**item_data.dict()))
    session.commit()  # ← 明示的な commit が必要！
    return item
```

**推奨対応**:

**オプション A: 明示的に commit する（推奨）**
```python
@router.post("/items")
def create_item(
    item_data: ItemCreate,
    session: Session = Depends(get_db_session)
):
    repo = ItemRepository(session)
    item = repo.save(Item(**item_data.dict()))
    session.commit()  # 明示的に commit
    return item
```

**オプション B: get_db_transaction() を使う**
```python
from repom.database import get_db_transaction

@router.post("/items")
def create_item(
    item_data: ItemCreate,
    session: Session = Depends(get_db_transaction)  # transaction に変更
):
    repo = ItemRepository(session)
    item = repo.save(Item(**item_data.dict()))
    # with ブロック終了時に自動 commit
    return item
```

**注意**: `get_db_transaction()` は FastAPI Depends では使用できません。`get_db_session()` + 明示的 commit を推奨します。

---

### 2. created_at/updated_at の即座の参照

**問題のあるコード**:
```python
# 外部セッション使用時
with _db_manager.get_sync_transaction() as session:
    repo = ItemRepository(session)
    item = repo.save(Item(name="test"))
    
    # ❌ created_at は None（refresh されていない）
    print(f"Created at: {item.created_at}")
```

**修正例**:
```python
# 明示的に refresh する
with _db_manager.get_sync_transaction() as session:
    repo = ItemRepository(session)
    item = repo.save(Item(name="test"))
    
    # ✅ 明示的に refresh
    session.refresh(item)
    print(f"Created at: {item.created_at}")
```

**または、内部セッションを使用**:
```python
# 内部セッション: 自動 refresh される
repo = ItemRepository()  # session=None
item = repo.save(Item(name="test"))

# ✅ created_at は自動設定される
print(f"Created at: {item.created_at}")
```

---

### 3. with 文でのトランザクション管理

**これは問題ありません**:
```python
# ✅ 問題なし: with 終了時に自動 commit
with _db_manager.get_sync_transaction() as session:
    repo = ItemRepository(session)
    item = repo.save(Item(name="test"))
    # with ブロック終了時に自動 commit
```

ただし、`created_at` / `updated_at` を使う場合は refresh が必要:
```python
with _db_manager.get_sync_transaction() as session:
    repo = ItemRepository(session)
    item = repo.save(Item(name="test"))
    
    # created_at を使う場合は refresh
    session.refresh(item)
    print(f"Created at: {item.created_at}")
```

---

## 🛠️ 修正手順

### Step 1: 外部セッション使用箇所を特定

```bash
# Repository に session を渡している箇所を検索
grep -r "Repository(.*session" src/
grep -r "Repository.*session=" src/
```

### Step 2: commit の有無を確認

各箇所で以下を確認：
- [ ] `save()` / `saves()` / `remove()` の後に `session.commit()` があるか？
- [ ] with 文を使っている場合、自動 commit されるか？
- [ ] FastAPI Depends の場合、commit が必要か？

### Step 3: created_at/updated_at の参照を確認

```bash
# created_at/updated_at の参照を検索
grep -r "\.created_at" src/
grep -r "\.updated_at" src/
```

各箇所で以下を確認：
- [ ] `save()` 直後に参照しているか？
- [ ] 外部セッション使用時か？
- [ ] refresh が必要か？

---

## 📝 コードパターン別対応表

| パターン | 変更前の動作 | 変更後の動作 | 対応 |
|---------|------------|------------|------|
| **内部セッション** | 自動 commit | 自動 commit | **不要** |
| **FastAPI + get_db_session** | 自動 commit | flush のみ | **session.commit() 追加** |
| **with get_sync_transaction** | 自動 commit | flush のみ（with 終了時 commit） | **不要** |
| **手動 session 管理** | 自動 commit | flush のみ | **session.commit() 追加** |
| **created_at 即座参照** | 自動 refresh | refresh なし | **session.refresh() 追加** |

---

## 🎯 mine-py プロジェクトでの確認ポイント

### 1. FastAPI エンドポイント

**確認すべきファイル**:
- `src/mine_py/routers/*.py`
- `src/mine_py/api/*.py`

**確認項目**:
```python
# このパターンを探す
@router.post("/...")
def endpoint(session: Session = Depends(get_db_session)):
    repo = SomeRepository(session)
    item = repo.save(...)  # ← commit が必要
    return item
```

**修正例**:
```python
@router.post("/...")
def endpoint(session: Session = Depends(get_db_session)):
    repo = SomeRepository(session)
    item = repo.save(...)
    session.commit()  # 追加
    return item
```

### 2. バックグラウンドタスク

**確認すべきファイル**:
- `src/mine_py/tasks/*.py`
- `src/mine_py/services/*.py`

**確認項目**:
```python
# with 文を使っている場合は通常 OK
with _db_manager.get_sync_transaction() as session:
    repo = SomeRepository(session)
    item = repo.save(...)
    # with 終了時に自動 commit（OK）
```

### 3. CLI スクリプト

**確認すべきファイル**:
- `src/mine_py/scripts/*.py`

**確認項目**:
- 内部セッションを使っている場合は影響なし
- 外部セッションの場合は commit が必要

---

## ⚠️ よくある問題と解決策

### 問題 1: データが保存されない

**症状**:
```python
item = repo.save(Item(name="test"))
# データベースに保存されない
```

**原因**: 外部セッション使用時、commit が実行されていない

**解決策**:
```python
item = repo.save(Item(name="test"))
session.commit()  # 追加
```

---

### 問題 2: created_at が None

**症状**:
```python
item = repo.save(Item(name="test"))
print(item.created_at)  # None
```

**原因**: 外部セッション使用時、refresh が実行されていない

**解決策**:
```python
item = repo.save(Item(name="test"))
session.refresh(item)  # 追加
print(item.created_at)  # OK
```

---

### 問題 3: FastAPI で "database is locked" エラー

**症状**: FastAPI エンドポイントで SQLite の "database is locked" エラー

**原因**: commit が実行されず、トランザクションが長時間開いたまま

**解決策**:
```python
@router.post("/items")
def create_item(session: Session = Depends(get_db_session)):
    repo = ItemRepository(session)
    item = repo.save(Item(name="test"))
    session.commit()  # これで解決
    return item
```

---

## 💡 ベストプラクティス

### 1. FastAPI では明示的に commit する

```python
@router.post("/items")
def create_item(
    item_data: ItemCreate,
    session: Session = Depends(get_db_session)
):
    try:
        repo = ItemRepository(session)
        item = repo.save(Item(**item_data.dict()))
        session.commit()  # 明示的に commit
        return item
    except Exception as e:
        session.rollback()  # エラー時は rollback
        raise
```

### 2. トランザクション管理は with 文で

```python
# ✅ 推奨: with 文でトランザクション管理
with _db_manager.get_sync_transaction() as session:
    repo = ItemRepository(session)
    item = repo.save(Item(name="test"))
    # with 終了時に自動 commit
```

### 3. DB 自動設定値が必要な場合は refresh

```python
item = repo.save(Item(name="test"))

# created_at/updated_at が必要な場合
session.refresh(item)
print(f"Created: {item.created_at}")
```

---

## 🔗 関連ドキュメント

- [セッション管理パターンガイド](../repository/repository_session_patterns.md)
- [トランザクション管理の詳細](../repository/repository_session_patterns.md#トランザクション管理の詳細)
- [BaseRepository ガイド](../repository/base_repository_guide.md)

---

## 📞 サポート

問題が解決しない場合は、以下の情報を含めて報告してください：

1. 使用パターン（FastAPI / CLI / バックグラウンドタスク）
2. エラーメッセージ
3. 関連するコードスニペット
4. repom のバージョン

---

**最終更新**: 2026-01-15
