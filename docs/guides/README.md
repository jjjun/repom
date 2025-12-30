# repom Guides

repom の使い方を機能別に整理したガイド集です。

## 📂 ガイドカテゴリ

### 🎨 [model/](model/) - モデル定義
- BaseModel の拡張機能
- Pydantic スキーマ自動生成
- システムカラムとカスタム型
- 論理削除（ソフトデリート）

### 📦 [repository/](repository/) - リポジトリパターン
- BaseRepository の使い方
- セッション管理パターン
- データベース接続とトランザクション
- AsyncBaseRepository

### ⚡ [features/](features/) - 機能別ガイド
- モデルの自動インポート
- マスターデータ同期
- ロギング

### 🧪 [testing/](testing/) - テスト
- Transaction Rollback パターン
- テストフィクスチャ

## 🎯 ガイドの使い方

1. **初めての方**: [repository/repository_and_utilities_guide.md](repository/repository_and_utilities_guide.md) から始めてください
2. **FastAPI統合**: [repository/repository_session_patterns.md](repository/repository_session_patterns.md) の FastAPI セクションを参照
3. **スキーマ生成**: [model/base_model_auto_guide.md](model/base_model_auto_guide.md) を参照
4. **テスト作成**: [testing/testing_guide.md](testing/testing_guide.md) を参照

## 📖 全ガイド一覧

### Model (3)
- [base_model_auto_guide.md](model/base_model_auto_guide.md)
- [system_columns_and_custom_types.md](model/system_columns_and_custom_types.md)
- [soft_delete_guide.md](model/soft_delete_guide.md)

### Repository (3)
- [async_repository_guide.md](repository/async_repository_guide.md)
- [repository_and_utilities_guide.md](repository/repository_and_utilities_guide.md)
- [repository_session_patterns.md](repository/repository_session_patterns.md)

### Features (3)
- [auto_import_models_guide.md](features/auto_import_models_guide.md)
- [logging_guide.md](features/logging_guide.md)
- [master_data_sync_guide.md](features/master_data_sync_guide.md)

### Testing (1)
- [testing_guide.md](testing/testing_guide.md)

---

**合計**: 10 ガイド
