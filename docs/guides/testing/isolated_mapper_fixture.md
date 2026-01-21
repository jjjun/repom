# isolated_mapper_registry フィクスチャガイド

一時的なモデル定義を行うテストで使用する専用フィクスチャのガイドです。

## 📋 目次

- [概要](#概要)
- [なぜ必要なのか](#なぜ必要なのか)
- [基本的な使い方](#基本的な使い方)
- [動作の仕組み](#動作の仕組み)
- [使用例](#使用例)
- [ベストプラクティス](#ベストプラクティス)
- [トラブルシューティング](#トラブルシューティング)

---

## 概要

**isolated_mapper_registry** は、テスト内で一時的な SQLAlchemy モデルを定義する際に使用する専用フィクスチャです。

### 特徴

✅ **自動クリーンアップ**: テスト終了後にマッパーを自動的にクリア  
✅ **他のテストへの影響なし**: 一時的なモデルが他のテストに干渉しない  
✅ **標準モデルの再構築**: クリーンアップ後、repom の標準モデルを自動的に再構築  
✅ **簡単に使える**: フィクスチャを受け取るだけでOK  

### 対象となるテスト

- TYPE_CHECKING ブロックのテスト
- モデル定義の動作検証
- Alembic マイグレーション生成テスト
- モデルの継承やリレーションシップのテスト

---

## なぜ必要なのか

### 問題: マッパーレジストリのグローバル汚染

SQLAlchemy のマッパーレジストリは**プロセス全体でグローバル**です：

```python
# テスト1: 一時的なモデルを定義
def test_temporary_model(db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        name: Mapped[str] = mapped_column(String(100))
    
    # TempModel が SQLAlchemy のグローバルレジストリに登録される
    # ✅ テスト1は成功

# テスト2: 別のテスト
def test_another_feature(db_test):
    # ❌ TempModel がまだレジストリに残っている
    # データはロールバックされるが、マッパー定義は残る
```

**問題点**:
- Transaction Rollback では**データのみロールバック**
- **マッパー定義**はロールバックされない
- 後続のテストでマッパーが衝突する可能性

### 解決策: isolated_mapper_registry フィクスチャ

```python
def test_temporary_model(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        name: Mapped[str] = mapped_column(String(100))
    
    # テスト実行
    # ...
    
    # テスト終了時、自動的に:
    # 1. TempModel をメタデータから削除
    # 2. マッパーレジストリをクリア
    # 3. 標準モデルを再構築
```

---

## 基本的な使い方

### 1. フィクスチャを受け取る

```python
def test_my_temporary_model(isolated_mapper_registry, db_test):
    """isolated_mapper_registry を受け取るだけ"""
    from repom.models import BaseModel
    from sqlalchemy import String
    from sqlalchemy.orm import Mapped, mapped_column
    
    # 一時的なモデル定義
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        name: Mapped[str] = mapped_column(String(100))
    
    # テーブル作成
    BaseModel.metadata.create_all(bind=db_test.bind)
    
    # テスト実行
    model = TempModel(name='Test')
    db_test.add(model)
    db_test.commit()
    
    assert model.id is not None
    # テスト終了時、自動クリーンアップ
```

### 2. クリーンアップは自動

```python
def test_first_temporary_model(isolated_mapper_registry, db_test):
    """最初のテスト"""
    class TempModel1(BaseModel):
        __tablename__ = 'temp_table_1'
        name: Mapped[str] = mapped_column(String(100))
    
    BaseModel.metadata.create_all(bind=db_test.bind)
    # ...
    # ✅ テスト終了時に TempModel1 がクリーンアップされる


def test_second_temporary_model(isolated_mapper_registry, db_test):
    """2番目のテスト"""
    # TempModel1 は残っていない（独立した環境）
    
    class TempModel2(BaseModel):
        __tablename__ = 'temp_table_2'
        name: Mapped[str] = mapped_column(String(100))
    
    BaseModel.metadata.create_all(bind=db_test.bind)
    # ...
    # ✅ テスト終了時に TempModel2 がクリーンアップされる
```

---

## 動作の仕組み

### フィクスチャの内部処理（改善版）

```python
@pytest.fixture
def isolated_mapper_registry(db_test):
    from sqlalchemy.orm import clear_mappers, configure_mappers
    from repom.models import BaseModel
    import importlib
    import sys
    
    # 【1】テスト実行前の状態を保存
    original_tables = set(BaseModel.metadata.tables.keys())
    
    yield  # ← テスト実行
    
    # 【2】クリーンアップ: 一時的なテーブルを削除
    temp_tables = set(BaseModel.metadata.tables.keys()) - original_tables
    for table_name in temp_tables:
        BaseModel.metadata.remove(BaseModel.metadata.tables[table_name])
    
    # 【3】マッパーをクリア（全マッパーがクリアされる）
    clear_mappers()
    
    # 【4】behavior_tests のモジュールレベルモデルを再ロード
    # これにより、clear_mappers() で無効化されたマッパーが再構築される
    behavior_test_modules = [
        'tests.behavior_tests.test_unique_key_handling',
        'tests.behavior_tests.test_date_type_comparison',
        'tests.behavior_tests.test_migration_no_id',
    ]
    for module_name in behavior_test_modules:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
    
    # 【5】repom の標準モデルを再ロード
    from repom.utility import load_models
    load_models()
    
    # 【6】マッパーを明示的に構築
    configure_mappers()
    
    # 【7】テーブルを再作成
    BaseModel.metadata.create_all(bind=db_test.bind)
```

### 処理フロー（改善版）

```
テスト開始
    ↓
isolated_mapper_registry 受け取り
    ↓
【1】現在のテーブル一覧を保存
    ↓
一時的なモデルを定義（TempModel）
    ↓
テーブル作成: BaseModel.metadata.create_all()
    ↓
テスト実行
    ↓
テスト終了
    ↓
【2】一時テーブルを metadata から削除
    ↓
【3】clear_mappers() で全マッパーをクリア
    ↓
【4】behavior_tests のモジュールを再ロード
    （RosterModel などのモジュールレベルモデルを再構築）
    ↓
【5】load_models() で repom の標準モデルを再ロード
    ↓
【6】configure_mappers() でマッパー再構築
    ↓
【7】標準モデルのテーブルを再作成
    ↓
次のテストへ（クリーンな状態）
```

**重要な改善点**:
- 【4】で behavior_tests のモジュールを明示的に再ロード
- これにより、test_unique_key_handling.py の RosterModel も再構築される
- テスト実行順序に依存しない
【1】現在のテーブル一覧を保存
    ↓
一時的なモデルを定義（TempModel）
    ↓
テーブル作成: BaseModel.metadata.create_all()
    ↓
テスト実行
    ↓
テスト終了
    ↓
【2】一時テーブルを metadata から削除
    ↓
【3】clear_mappers() でマッパーをクリア
    ↓
【4】load_models() で標準モデルを再ロード
    ↓
【5】configure_mappers() でマッパー再構築
    ↓
【6】標準モデルのテーブルを再作成
    ↓
次のテストへ（クリーンな状態）
```

---

## 使用例

### 例1: TYPE_CHECKING ブロックのテスト

```python
def test_type_checking_with_forward_reference(isolated_mapper_registry, db_test):
    """TYPE_CHECKING ブロック内で前方参照を使用するテスト"""
    from typing import TYPE_CHECKING
    from repom.models import BaseModelAuto
    from sqlalchemy import String, Integer, ForeignKey
    from sqlalchemy.orm import Mapped, mapped_column, relationship
    
    if TYPE_CHECKING:
        from __future__ import annotations  # 前方参照を有効化
    
    class ParentModel(BaseModelAuto):
        __tablename__ = 'test_parent'
        name: Mapped[str] = mapped_column(String(100))
        # TYPE_CHECKING 内で ChildModel を参照
        children: Mapped[list['ChildModel']] = relationship(back_populates='parent')
    
    class ChildModel(BaseModelAuto):
        __tablename__ = 'test_child'
        name: Mapped[str] = mapped_column(String(100))
        parent_id: Mapped[int] = mapped_column(ForeignKey('test_parent.id'))
        parent: Mapped['ParentModel'] = relationship(back_populates='children')
    
    # テーブル作成
    BaseModelAuto.metadata.create_all(bind=db_test.bind)
    
    # テスト実行
    parent = ParentModel(name='Parent')
    child = ChildModel(name='Child', parent=parent)
    db_test.add(parent)
    db_test.commit()
    
    # リレーションシップが正しく動作するか確認
    assert len(parent.children) == 1
    assert child.parent.name == 'Parent'
```

### 例2: Alembic マイグレーションテスト

```python
def test_alembic_migration_generation(isolated_mapper_registry, db_test):
    """use_id=False のモデルでマイグレーション生成をテスト"""
    from repom.models import BaseModel
    from sqlalchemy import String
    from sqlalchemy.orm import Mapped, mapped_column
    
    class MigrationTestModel(BaseModel):
        __tablename__ = 'migration_test'
        use_id = False
        
        code: Mapped[str] = mapped_column(String(50), primary_key=True)
        name: Mapped[str] = mapped_column(String(100))
    
    # マイグレーションファイル生成のテスト
    # ...
```

### 例3: モデル継承のテスト

```python
def test_model_inheritance(isolated_mapper_registry, db_test):
    """モデル継承が正しく動作するかテスト"""
    from repom.models import BaseModel
    from sqlalchemy import String, Integer
    from sqlalchemy.orm import Mapped, mapped_column
    
    class BaseAnimal(BaseModel):
        __tablename__ = 'animals'
        type: Mapped[str] = mapped_column(String(50))
        name: Mapped[str] = mapped_column(String(100))
        __mapper_args__ = {
            'polymorphic_on': type,
            'polymorphic_identity': 'animal'
        }
    
    class Dog(BaseAnimal):
        __mapper_args__ = {
            'polymorphic_identity': 'dog'
        }
        bark_volume: Mapped[int] = mapped_column(Integer, nullable=True)
    
    class Cat(BaseAnimal):
        __mapper_args__ = {
            'polymorphic_identity': 'cat'
        }
        meow_pitch: Mapped[int] = mapped_column(Integer, nullable=True)
    
    BaseModel.metadata.create_all(bind=db_test.bind)
    
    # テスト実行
    dog = Dog(name='Buddy', bark_volume=10)
    cat = Cat(name='Whiskers', meow_pitch=5)
    db_test.add_all([dog, cat])
    db_test.commit()
    
    # Polymorphic クエリのテスト
    animals = db_test.query(BaseAnimal).all()
    assert len(animals) == 2
    assert isinstance(animals[0], (Dog, Cat))
```

---

## ベストプラクティス

### 1. 必要な場合のみ使用

```python
# ✅ Good: 一時的なモデルを定義する場合
def test_temporary_model(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        # ...

# ❌ Bad: 標準モデルだけを使う場合（不要）
def test_standard_model(isolated_mapper_registry, db_test):
    from repom.examples.models import User
    user = User(name='Test')
    db_test.add(user)
    # isolated_mapper_registry は不要
```

**理由**: 不要なオーバーヘッド（マッパー再構築）を避ける

### 2. テーブル作成を忘れずに

```python
# ✅ Good
def test_with_table_creation(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        name: Mapped[str] = mapped_column(String(100))
    
    # テーブル作成
    BaseModel.metadata.create_all(bind=db_test.bind)
    
    # テスト実行
    model = TempModel(name='Test')
    db_test.add(model)

# ❌ Bad: テーブル作成を忘れる
def test_without_table_creation(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        name: Mapped[str] = mapped_column(String(100))
    
    # テーブル作成を忘れている
    model = TempModel(name='Test')
    db_test.add(model)  # OperationalError: no such table
```

### 3. docstring で目的を明記

```python
def test_type_checking_pattern(isolated_mapper_registry, db_test):
    """TYPE_CHECKING ブロックで前方参照を使用するパターンをテスト
    
    検証内容:
    - ParentModel と ChildModel の双方向リレーションシップ
    - TYPE_CHECKING 内での 'ChildModel' 文字列参照
    - configure_mappers() での前方参照解決
    """
    # ...
```

### 4. クリーンアップコードを書かない

```python
# ✅ Good: フィクスチャに任せる
def test_temporary_model(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        # ...
    
    # テスト実行
    # クリーンアップは自動

# ❌ Bad: 手動でクリーンアップ（不要）
def test_temporary_model(isolated_mapper_registry, db_test):
    try:
        class TempModel(BaseModel):
            __tablename__ = 'temp_table'
            # ...
    finally:
        clear_mappers()  # 不要（フィクスチャが行う）
```

---

## トラブルシューティング

### 問題1: "no such table" エラー

**症状**:
```
sqlalchemy.exc.OperationalError: no such table: temp_table
```

**原因**: テーブル作成を忘れている

**解決策**:
```python
def test_fix(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        name: Mapped[str] = mapped_column(String(100))
    
    # ✅ これを追加
    BaseModel.metadata.create_all(bind=db_test.bind)
    
    model = TempModel(name='Test')
    db_test.add(model)
```

### 問題2: 後続のテストで "Table 'xxx' is already defined" エラー

**症状**:
```
sqlalchemy.exc.InvalidRequestError: Table 'temp_table' is already defined for this MetaData instance.
```

**原因**: `isolated_mapper_registry` フィクスチャを受け取っていない

**解決策**:
```python
# ❌ Bad
def test_temporary_model(db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        # ...

# ✅ Good
def test_temporary_model(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp_table'
        # ...
```

### 問題3: パフォーマンスへの影響

**症状**: テストが遅くなった

**原因**: 不要なテストで `isolated_mapper_registry` を使っている

**解決策**:
```python
# ✅ 一時的なモデルを定義する場合のみ使用
def test_temporary_model(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        # ...

# ✅ 標準モデルだけなら不要
def test_standard_model(db_test):
    from repom.examples.models import User
    user = User(name='Test')
    # isolated_mapper_registry は不要
```

**ベンチマーク**:
- `isolated_mapper_registry` なし: ~5ms/テスト
- `isolated_mapper_registry` あり: ~50ms/テスト

**推奨**: 一時的なモデル定義が必要な2-3個のテストのみに使用

### 問題4: 他のテストに影響が出る

**症状**: `isolated_mapper_registry` を使うテストの後、他のテストが失敗

**原因**: `isolated_mapper_registry` の実装バグ（報告してください）

**一時的な解決策**:
```python
def test_workaround(isolated_mapper_registry, db_test):
    # テスト実行
    # ...
    
    # 手動で標準モデルを再ロード（通常は不要）
    from repom.utility import load_models
    from sqlalchemy.orm import configure_mappers
    load_models()
    configure_mappers()
```

---

## 参考リンク

- [fixture_guide.md](fixture_guide.md) - フィクスチャの基本的な使い方
- [testing_guide.md](testing_guide.md) - repom のテスト戦略
- [SQLAlchemy Mapper Configuration](https://docs.sqlalchemy.org/en/20/orm/mapper_config.html)
- [pytest fixtures 公式ドキュメント](https://docs.pytest.org/en/stable/fixture.html)

---

## 実装例

repom での実際の使用例：

- [tests/conftest.py](../../tests/conftest.py) - フィクスチャの実装
- [tests/behavior_tests/test_type_checking_import_order.py](../../tests/behavior_tests/test_type_checking_import_order.py) - TYPE_CHECKING テスト
- [tests/behavior_tests/test_type_checking_detailed.py](../../tests/behavior_tests/test_type_checking_detailed.py) - 詳細な TYPE_CHECKING テスト

---

**最終更新**: 2025-12-30
