# repom Guides

repom の使い方を機能別に整理したガイド集です。

## 📂 ガイドカテゴリ

### 🔧 [core/](core/) - コア機能
- BaseModel の拡張機能
- Pydantic スキーマ自動生成
- カスタム型の実装
- モデル自動インポート

### 💾 [database/](database/) - データベース
- database.py の使い方
- 移行ガイド

### 📦 [repository/](repository/) - リポジトリパターン
- BaseRepository の使い方
- セッション管理パターン
- AsyncBaseRepository

### ⚡ [features/](features/) - 機能別ガイド
- ソフトデリート
- マスターデータ同期
- ロギング

### 🧪 [testing/](testing/) - テスト
- Transaction Rollback パターン
- テストフィクスチャ

## 🎯 ガイドの使い方

1. **初めての方**: [repository/repository_and_utilities_guide.md](repository/repository_and_utilities_guide.md) から始めてください
2. **FastAPI統合**: [repository/repository_session_patterns.md](repository/repository_session_patterns.md) の FastAPI セクションを参照
3. **スキーマ生成**: [core/base_model_auto_guide.md](core/base_model_auto_guide.md) を参照
4. **テスト作成**: [testing/testing_guide.md](testing/testing_guide.md) を参照

## 📖 全ガイド一覧

### Core (3)
- [auto_import_models_guide.md](core/auto_import_models_guide.md)
- [base_model_auto_guide.md](core/base_model_auto_guide.md)
- [system_columns_and_custom_types.md](core/system_columns_and_custom_types.md)

### Database (1)
- [migration_to_database_py.md](database/migration_to_database_py.md)

### Repository (3)
- [async_repository_guide.md](repository/async_repository_guide.md)
- [repository_and_utilities_guide.md](repository/repository_and_utilities_guide.md)
- [repository_session_patterns.md](repository/repository_session_patterns.md)

### Features (3)
- [logging_guide.md](features/logging_guide.md)
- [master_data_sync_guide.md](features/master_data_sync_guide.md)
- [soft_delete_guide.md](features/soft_delete_guide.md)

### Testing (1)
- [testing_guide.md](testing/testing_guide.md)

---

**合計**: 11 ガイド (削減前: 13 ガイド)
