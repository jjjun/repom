# Model Guides

このディレクトリには、repom のモデル（BaseModel）に関するガイドとカラム定義系のドキュメントが含まれています。

## 📚 ガイド一覧

### BaseModel 関連

- **[base_model_auto_guide.md](base_model_auto_guide.md)** - BaseModelAuto による Pydantic スキーマ自動生成
  - get_create_schema() / get_update_schema() / get_response_schema()
  - @response_field デコレータの使い方
  - 前方参照の解決方法
  - FastAPI 統合の実装例

### カラム定義ガイド

- **[system_columns_and_custom_types.md](system_columns_and_custom_types.md)** - システムカラムとカスタム型
  - use_id, use_created_at, use_updated_at などのシステムカラム
  - AutoDateTime, ISO8601DateTime などのカスタム型
  - カラムの設定方法と使用例

- **[soft_delete_guide.md](soft_delete_guide.md)** - 論理削除機能
  - SoftDeletableMixin の使い方
  - deleted_at カラムの自動管理
  - BaseRepository との統合
  - 論理削除のベストプラクティス

## 🔗 関連ドキュメント

- [Repository Guides](../repository/) - リポジトリ層のガイド
- [Testing Guides](../testing/) - テスト戦略とベストプラクティス
- [Core Guides](../core/) - 設定とユーティリティ

---

**参考**: モデルの基本的な使い方については、プロジェクトルートの [README.md](../../../README.md) も参照してください。
