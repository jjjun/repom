# SQLAlchemy Relationship Resolution Issue in repom

## 問題概要

`repom` パッケージの `BaseModel.get_response_schema()` メソッドを呼び出すと、SQLAlchemy の relationship 解決時に循環参照エラーが発生する問題です。

### エラーメッセージ
```
sqlalchemy.exc.InvalidRequestError: When initializing mapper Mapper[AniWikiTvListModel(ani_wiki_tv_lists)], expression 'AniWikiTvListAiModel' failed to locate a name ('AniWikiTvListAiModel'). If this is a class name, consider adding this relationship() to the <class 'src.models.ani_wiki_tv_list.AniWikiTvListModel'> class after both dependent classes have been defined.
```

## 問題の詳細

### 発生条件
1. `mine_db` から `repom` に移行した環境
2. SQLAlchemy の `relationship()` で相互参照があるモデル
3. `BaseModel.get_response_schema()` メソッドを呼び出した時

### 問題の流れ
```
AssetItemTagModel.get_response_schema()
↓
repom/base_model.py:188 - inspect(cls).mapper.column_attrs
↓
SQLAlchemy が全モデルのマッパーを初期化
↓
AniWikiTvListModel の relationship で AniWikiTvListAiModel を探す
↓
AniWikiTvListAiModel がレジストリに見つからない → エラー
```

### 重要な観察事項
- **直接関係のないモデル同士でエラーが発生**
  - `AssetItemTagModel` は `AniWikiTvListAiModel` と直接関係ない
  - SQLAlchemy は **グローバルレジストリ** を使用するため、一つのモデルのスキーマ生成で全モデルの関係性を解決しようとする

## 再現方法

### 環境
- Python 3.12
- SQLAlchemy 2.x
- repom パッケージ (mine_db からの移行版)

### 再現コード
```python
# 1. モデル単体では問題なし
from src.models.asset_item_tag import AssetItemTagModel
from src.models.ani_wiki_tv_list import AniWikiTvListModel
from src.models.ani_wiki_tv_list_ai import AniWikiTvListAiModel

print("All models import successfully")  # ← これは成功

# 2. get_response_schema() でエラー発生
response_schema = AssetItemTagModel.get_response_schema()  # ← ここでエラー
```

### モデル構造例
```python
# AniWikiTvListModel
class AniWikiTvListModel(BaseModel):
    ani_wiki_tv_list_ais = relationship(
        'AniWikiTvListAiModel',  # ← この文字列参照が解決できない
        back_populates='ani_wiki_tv_list'
    )

# AniWikiTvListAiModel  
class AniWikiTvListAiModel(BaseModel):
    ani_wiki_tv_list = relationship(
        'AniWikiTvListModel',
        back_populates='ani_wiki_tv_list_ais'
    )
```

## 調査が必要な箇所

### 1. repom/base_model.py の get_response_schema() メソッド

**該当コード:**
```python
# Line 188 in repom/base_model.py
for column in inspect(cls).mapper.column_attrs:
```

**問題:**
- `inspect(cls).mapper.column_attrs` が SQLAlchemy の全マッパー初期化を引き起こす
- レジストリ内のクラス解決タイミングの問題

### 2. SQLAlchemy レジストリの動作確認

**確認事項:**
```python
# レジストリの状態確認
registry = AssetItemTagModel.registry
registry_keys = list(registry._class_registry.data.keys())
print("AniWikiTvListAiModel" in registry_keys)  # False になっている
```

### 3. mine_db との違い

**mine_db では正常動作していた理由:**
- インポート順序やレジストリ登録の違い
- SQLAlchemy バージョンの差異の可能性

## 想定される解決方向性

### Option 1: get_response_schema() の改善
```python
def get_response_schema(cls):
    try:
        # 現在の実装
        for column in inspect(cls).mapper.column_attrs:
            # ...
    except InvalidRequestError:
        # レジストリ問題をハンドリング
        # 全モデルを強制的に読み込んでリトライ
        import_all_models()
        return cls.get_response_schema()
```

### Option 2: 遅延評価の活用
```python
def get_response_schema(cls):
    # SQLAlchemy マッパーの遅延初期化
    from sqlalchemy.orm import configure_mappers
    configure_mappers()  # 全マッパーを事前に設定
    
    for column in inspect(cls).mapper.column_attrs:
        # ...
```

### Option 3: レジストリ管理の改善
- `repom` パッケージ内でのモデルレジストリ管理方法の見直し
- `mine_db` との互換性を保つためのレジストリ初期化順序の調整

## 追加調査用の診断情報

### SQLAlchemy レジストリの状態
```python
# 実行時のレジストリ内容
from src.models.asset_item_tag import AssetItemTagModel
registry_keys = list(AssetItemTagModel.registry._class_registry.data.keys())
ani_related = [key for key in registry_keys if 'Ani' in key]
print(f"Ani-related classes in registry: {ani_related}")
# Output: ['AniVideoTagModel', 'AniVideoTagLinkModel', ..., 'AniWikiTvListModel']
# Missing: AniWikiTvListAiModel
```

### インポート順序の検証
```python
# src/models/__init__.py での定義順序
from .ani_wiki_tv_list_ai import AniWikiTvListAiModel  # 先にインポート
from .ani_wiki_tv_list import AniWikiTvListModel       # 後にインポート
```

## 期待される成果

1. `repom` パッケージでの SQLAlchemy relationship 解決問題の修正
2. `mine_db` からの移行時の互換性向上
3. `get_response_schema()` メソッドの堅牢性向上

## 連絡先・追加情報

問題の詳細や追加の再現コードが必要な場合は、mine-py プロジェクトの担当者まで連絡してください。

**プロジェクト:** mine-py  
**ブランチ:** migrate/mine-db-to-repom  
**関連ファイル:**
- `src/models/__init__.py` - モデルインポート定義
- `src/api/schemas/asset_man.py` - エラー発生箇所
- `src/models/ani_wiki_tv_list*.py` - 問題のモデル定義