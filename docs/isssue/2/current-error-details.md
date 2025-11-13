# Current Error Details - mine-py Project

## 実際のエラー情報

### 発生日時
2025年11月13日

### 環境情報
- **Python**: 3.12.8
- **SQLAlchemy**: 2.x系
- **Project**: mine-py (migrate/mine-db-to-repom branch)
- **Issue**: mine_db → repom パッケージ移行時の SQLAlchemy relationship 解決エラー

### 完全なエラーメッセージ
```
sqlalchemy.exc.InvalidRequestError: When initializing mapper Mapper[AniWikiTvListModel(ani_wiki_tv_lists)], expression 'AniWikiTvListAiModel' failed to locate a name ('AniWikiTvListAiModel'). If this is a class name, consider adding this relationship() to the <class 'src.models.ani_wiki_tv_list.AniWikiTvListModel'> class after both dependent classes have been defined.
```

### スタックトレース（重要部分）
```
File "src/api/schemas/asset_man.py", line 170, in <module>
    AssetItemTagResponse = AssetItemTagModel.get_response_schema()
File "submod/repom/repom/base_model.py", line 188, in get_response_schema
    for column in inspect(cls).mapper.column_attrs:
File "sqlalchemy/orm/mapper.py", line 3172, in column_attrs
    return self._filter_properties(properties.ColumnProperty)
File "sqlalchemy/orm/mapper.py", line 3225, in _filter_properties
    self._check_configure()
File "sqlalchemy/orm/mapper.py", line 2401, in _check_configure
    _configure_registries({self.registry}, cascade=True)
```

### 実際の問題モデル定義

#### AniWikiTvListModel (src/models/ani_wiki_tv_list.py)
```python
class AniWikiTvListModel(BaseModel, VideoLinkMixin):
    __tablename__ = "ani_wiki_tv_lists"
    
    # ... other fields ...
    
    ani_wiki_tv_list_ais = relationship(
        'AniWikiTvListAiModel',  # ← この文字列参照が解決できない
        back_populates='ani_wiki_tv_list',
        cascade="all, delete-orphan"
    )
```

#### AniWikiTvListAiModel (src/models/ani_wiki_tv_list_ai.py)  
```python
class AniWikiTvListAiModel(BaseModel):
    __tablename__ = "ani_wiki_tv_list_ais"
    
    # ... other fields ...
    
    ani_wiki_tv_list_id = Column(Integer, ForeignKey('ani_wiki_tv_lists.id'), nullable=False)
    ani_wiki_tv_list = relationship(
        'AniWikiTvListModel',
        back_populates='ani_wiki_tv_list_ais',
        uselist=False,
    )
```

### トリガーとなったコード
```python
# src/api/schemas/asset_man.py (Line 170)
AssetItemTagResponse = AssetItemTagModel.get_response_schema()
```

### 重要な観察
1. **AssetItemTagModel と AniWikiTvListAiModel は直接関係ない**
   - 異なるドメインのモデル
   - 直接的な relationship は存在しない

2. **SQLAlchemy グローバルレジストリが原因**
   - 一つのモデルで `get_response_schema()` を呼ぶと全モデルのマッパーが初期化される
   - レジストリ内で `AniWikiTvListAiModel` が見つからない

3. **レジストリの実際の状態**
   ```python
   # 確認済みレジストリ内容（37クラス）
   ['AniVideoTagModel', 'AniVideoTagLinkModel', 'AniVideoResourceModel', 
    'AniVideoResourceLinkModel', 'AniVideoItemModel', 'AniVideoLinkModel', 
    'AniWikiTvListModel',  # ← 存在する
    'AniWikiTvGroupModel', 'AniWikiChangeLogModel', 'AniJwListItemModel', 
    'AniJwListLogGroupModel', 'AniJwListLogModel']
   # AniWikiTvListAiModel が含まれていない ← 問題の根本原因
   ```

### 試行した解決方法

#### ❌ 失敗した方法
1. **インポート順序の変更** - 効果なし
2. **`import src.models` の事前実行** - 効果なし  
3. **遅延実行** - まだ完全テストしていない

#### ✅ 動作確認済み
- モデル単体のインポートは全て成功
- テーブル定義も正常
- `get_response_schema()` 以外の操作は問題なし

### repom チームへの依頼事項

1. **`repom/base_model.py` の `get_response_schema()` メソッドの改善**
   - SQLAlchemy relationship 解決エラーのハンドリング
   - レジストリ問題の回避策

2. **SQLAlchemy レジストリ管理の見直し**
   - `mine_db` との互換性確保
   - クラス登録タイミングの最適化

3. **エラー診断とフィードバック**
   - 提供した診断スクリプトでの問題再現
   - 解決策の提案とテスト

### 連絡先
- GitHub: jjjun/py-mine
- Branch: migrate/mine-db-to-repom
- 担当: mine-py development team