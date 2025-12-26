# Issue Tracker - repom

このディレクトリは、repom プロジェクトの改善提案と課題管理のためのドキュメントを格納します。

## ディレクトリ構造

```
docs/issue/
├── README.md              # このファイル、Issue 管理のインデックス
├── active/                # 実装予定・作業中の Issue
│   └── XXX_*.md          # Issue（着手前または作業中）
└── completed/             # 完了・解決済み Issue
    ├── 001_*.md          # Issue #1（完了済）
    ├── 002_*.md          # Issue #2（完了済）
    └── 003_*.md          # Issue #3（完了済）
```

## Issue ライフサイクル

```
active/        → 実装予定・作業中（着手前 + 進行中）
    ↓
completed/     → 実装完了・コミット済み
```

## 🚧 実装予定・作業中の Issue

| ID | タイトル | 優先度 | ステータス | ファイル |
|----|---------|--------|-----------|---------||
| #017 | クエリ構築機能のMixin化によるコード一貫性向上 | 低 | 🔴 未着手 | [active/017_extract_query_builder_to_mixin.md](active/017_extract_query_builder_to_mixin.md) |
| #015 | Database Manager Unification - セッション・エンジン管理の統合 | 高 | 🔴 未着手 | [active/015_database_manager_unification.md](active/015_database_manager_unification.md) |
| #007 | Annotation Inheritance の実装検証 | 中 | 📝 調査待機中 | [active/007_annotation_inheritance_validation.md](active/007_annotation_inheritance_validation.md) |

詳細は各ファイルを参照してください。

---

## 📋 完了済み Issue

| ID | タイトル | 完了日 | 概要 | ファイル |
|----|---------|--------|------|---------|
| #015 | 論理削除機能のMixin化によるコード可読性向上 | 2025-12-26 | SoftDeleteRepositoryMixin作成、base_repository約150行削減、テスト全パス | [completed/015_extract_soft_delete_to_mixin.md](completed/015_extract_soft_delete_to_mixin.md) |
| #001 | FastAPI Depends互換性修正 | 2025-12-25 | @contextmanager削除、generator protocol復元、15テスト全パス | [completed/001_fastapi_depends_fix.md](completed/001_fastapi_depends_fix.md) |
| #014 | repom への論理削除（Soft Delete）機能追加 | 2025-12-10 | SoftDeletableMixin、BaseRepository拡張、22テスト全パス | [completed/014_soft_delete_feature.md](completed/014_soft_delete_feature.md) |
| #013 | マスターデータ同期コマンドの追加 | 2025-11-19 | db_sync_master コマンド、Upsert 操作、12テスト全パス | [completed/013_master_data_sync_command.md](completed/013_master_data_sync_command.md) |
| #012 | ロギング機能の追加 | 2025-01-XX | ハイブリッドアプローチロギング、CLI/アプリ対応、6テスト全パス | [completed/012_add_logging_support.md](completed/012_add_logging_support.md) |
| #011 | セッション管理ユーティリティの追加 | 2025-11-18 | トランザクション管理機能、FastAPI/CLI対応、13テスト全パス | [completed/011_session_management_utilities.md](completed/011_session_management_utilities.md) |
| #010 | BaseModel への UUID サポート追加 | 2025-11-18 | UUID 主キーサポート、BaseRepository 互換、17テスト全パス | [completed/010_add_uuid_support_to_base_model.md](completed/010_add_uuid_support_to_base_model.md) |
| #009 | テストインフラストラクチャの改善 | 2025-11-16 | Transaction Rollback パターン実装、9倍高速化達成 | [completed/009_test_infrastructure_improvement.md](completed/009_test_infrastructure_improvement.md) |
| #008 | Alembic マイグレーションファイルの保存場所制御 | 2025-11-16 | version_locations の一元管理、外部プロジェクト対応 | [completed/008_alembic_migration_path_conflict.md](completed/008_alembic_migration_path_conflict.md) |
| #006 | SQLAlchemy 2.0 スタイルへの移行 | 2025-11-15 | Mapped[] + mapped_column() 移行、型安全性向上 | [completed/006_migrate_to_sqlalchemy_2_0_style.md](completed/006_migrate_to_sqlalchemy_2_0_style.md) |
| #005 | 柔軟な auto_import_models 設定 | 2025-11-15 | 複数モデルディレクトリ対応、セキュリティ検証実装 | [completed/005_flexible_auto_import_models.md](completed/005_flexible_auto_import_models.md) |
| #003 | response_field 機能を BaseModelAuto に移行 | 2025-11-15 | スキーマ生成一元化、ドキュメント整備 | [completed/003_response_field_migration_to_base_model_auto.md](completed/003_response_field_migration_to_base_model_auto.md) |
| #002 | SQLAlchemy カラム継承制約による use_id 設計の課題 | 2025-11-14 | 複合主キー対応、抽象クラス制約解決 | [completed/002_sqlalchemy_column_inheritance_constraint.md](completed/002_sqlalchemy_column_inheritance_constraint.md) |
| #001 | get_response_schema() の前方参照改善 | 2025-11-14 | 前方参照自動解決、エラーメッセージ改善 | [completed/001_get_response_schema_forward_refs_improvement.md](completed/001_get_response_schema_forward_refs_improvement.md) |

詳細は各ファイルを参照してください。

---

## 新しい Issue の作成

新しい Issue を作成する際は:

1. **Active 段階**: `active/XXX_issue_name.md` にファイル作成
2. **完了**: 完了時に `completed/NNN_issue_name.md` へ移動（連番付与）

完了済み Issue には連番（001, 002, 003...）を付与してください。

---

## 🔧 Issue テンプレート

新しい Issue を追加する際は、以下のフォーマットを使用してください：

```markdown
# Issue #N: [タイトル]

**ステータス**: 🔴 未着手 / 🟡 提案中 / 🟢 進行中 / ✅ 完了

**作成日**: YYYY-MM-DD

**優先度**: 高 / 中 / 低

## 問題の説明

[現状の問題点を説明]

## 提案される解決策

[解決策の提案]

## 影響範囲

- 影響を受けるファイル
- 影響を受ける機能

## 実装計画

1. ステップ1
2. ステップ2
3. ...

## テスト計画

[テスト戦略とテストケースの説明]

## 関連リソース

- 関連ファイル
- 参考資料
```

---

## 🎯 Issue 管理の方針

### Issue の作成
- 改善提案、バグ報告、機能追加リクエストなどを Issue として管理
- 1つの Issue につき1つのマークダウンファイルを作成
- ファイル名は `[issue_name].md` の形式（スネークケース推奨）

### ステータス管理
- 🔴 **未着手**: Issue が提起されたが作業開始していない
- 🟡 **提案中**: 設計や調査中
- 🟢 **進行中**: 実装作業中
- ✅ **完了**: 実装、テスト、ドキュメント化が完了

### 優先度
- **高**: 重大な問題、ブロッカー
- **中**: 重要だが緊急ではない
- **低**: 改善提案、将来的な機能

---

## 📝 Issue の更新

Issue の進捗があった場合は、該当ファイルを更新し、この README.md の一覧も更新してください。

---

**次のステップ**: Phase 2（mine-py での適用）は別途実施

---

最終更新: 2025-12-10
