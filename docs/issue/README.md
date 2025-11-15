# Issue Tracker - repom

このディレクトリは、repom プロジェクトの改善提案と課題管理のためのドキュメントを格納します。

## ディレクトリ構造

```
docs/issue/
├── README.md              # このファイル（Issue 管理インデックス）
├── completed/             # 完了・解決済み Issue
│   ├── 001_*.md          # Issue #1（完了）
│   ├── 002_*.md          # Issue #2（完了）
│   └── 003_*.md          # Issue #3（完了）
├── in_progress/           # 作業中の Issue
└── backlog/               # 計画中・未着手の Issue
```

## Issue ライフサイクル

```
backlog/       → 計画と優先度付け
    ↓
in_progress/   → 実装作業中
    ↓
completed/     → 実装完了・テスト済み
```

## 🚧 作業中の Issue

### Issue #4: 柔軟な auto_import_models 設定

**ファイル**: `in_progress/004_flexible_auto_import_models.md`

**ステータス**: 🚧 作業中（2025-11-15）

**概要**:
設定ファイルで複数のモデルディレクトリを指定できるようにし、`models/__init__.py` への手動記述を不要にする。これにより、Alembic マイグレーションと db コマンドでのモデル認識ミスを防ぐ。

**実装予定**:
- Phase 1: 基本機能（高優先度）
  - [ ] `auto_import_models_by_package` 関数の実装
  - [ ] `auto_import_models_from_list` 関数の実装
  - [ ] `MineDbConfig.model_locations` プロパティ追加
  - [ ] `load_models()` 関数の修正
  - [ ] 単体テストの作成
- Phase 2: 統合とドキュメント
  - [ ] 統合テスト
  - [ ] ドキュメント更新

**技術的決定事項**:
- 環境変数は使わず config.py で完結
- CONFIG_HOOK で親プロジェクトが柔軟に設定可能
- `load_models()` 修正のみで全体に反映
- 後方互換性を維持

---

## 📝 計画中の Issue

現在、backlog に Issue はありません。

---

## 📋 完了済み Issue

### Issue #3: response_field 機能を BaseModelAuto に移行

**ファイル**: `completed/003_response_field_migration_to_base_model_auto.md`

**ステータス**: ✅ 完了（2025-11-15）

**概要**:
Response スキーマ生成機能を `BaseModel` から `BaseModelAuto` に移行し、Create/Update/Response の3つのスキーマ生成を一元化。Phase 6（ドキュメント更新）まで完了。

**実装内容**:
- Phase 1: 調査と準備 ✅
- Phase 2: BaseModelAuto への移行 ✅
- Phase 2.5: システムカラムの自動更新と保護 ✅
- Phase 3: `info['in_response']` の実装 ✅
- Phase 4: BaseModel からの削除とカスタム型リネーム（保留）
- Phase 5: テスト（全テスト合格）✅
- Phase 6: ドキュメント更新 ✅
  - `docs/guides/base_model_auto_guide.md` 作成（800行）
  - `docs/guides/repository_and_utilities_guide.md` 作成（600行）
  - `README.md` 簡略化（1,388行 → 291行）
  - `.github/copilot-instructions.md` 更新
  - `docs/technical/ai_context_management.md` 作成
- Phase 7: 外部プロジェクトへの移行通知（未実施）

**ドキュメント成果物**:
- 2つの包括的なガイド（base_model_auto_guide.md, repository_and_utilities_guide.md）
- AI エージェントが効率的に参照できる構造
- トークン消費量の最適化（29%で全ガイド同時アクセス可能）

**関連ドキュメント**:
- 実装ガイド: `docs/guides/base_model_auto_guide.md`
- リポジトリガイド: `docs/guides/repository_and_utilities_guide.md`
- 技術詳細: `docs/technical/get_response_schema_technical.md`
- AI コンテキスト管理: `docs/technical/ai_context_management.md`

### Issue #1: get_response_schema() の前方参照改善

**ファイル**: `completed/001_get_response_schema_forward_refs_improvement.md`

**ステータス**: ✅ 完了（2025-11-14）

**概要**:
`BaseModel.get_response_schema()` メソッドの前方参照解決改善。Phase 1（標準型の自動解決）と Phase 2（エラーメッセージ改善 + 環境別エラーハンドリング）を実装。

**結果**:
- Phase 1: 標準型（List, Dict, Optional 等）の自動解決
- Phase 2: 未定義型の自動検出とエラーメッセージ改善
- テスト: 31/31 パス（Phase 1: 3テスト + Phase 2: 4テスト）
- ドキュメント: 包括的な README セクション + research ディレクトリ

**関連ドキュメント**:
- 調査: `docs/research/auto_forward_refs_resolution.md`
- 実装: メイン `README.md` の Phase 1 & 2 セクション参照
- 技術詳細: `docs/technical/get_response_schema_technical.md`

### Issue #2: SQLAlchemy カラム継承制約による use_id 設計の課題

**ファイル**: `completed/002_sqlalchemy_column_inheritance_constraint.md`

**ステータス**: ✅ 完了（2025-11-14）

**概要**:
`BaseModel` と `BaseModelAuto` で `use_id` パラメータのデフォルト値を制御する際、SQLAlchemy のカラム継承制約により複合主キーモデルで `id` カラムが意図せず継承される問題を解決。

**結果**:
- 抽象クラス（`__tablename__` なし）にはカラムを追加しない設計
- 具象クラスのみに `use_id` に基づいて `id` カラムを追加
- `BaseModel` と `BaseModelAuto` の両方でデフォルト `use_id=True` を維持
- 複合主キーモデルで `use_id=False` を明示的に指定すれば `id` カラムなし
- テスト: 全 103 テスト合格

**関連ドキュメント**:
- 実装: `repom/base_model.py` と `repom/base_model_auto.py`
- テスト: `tests/unit_tests/test_model_no_id.py`

---

## 新しい Issue の作成

新しい Issue を作成する際は:

1. **Backlog 段階**: `backlog/XXX_issue_name.md` にファイル作成
2. **作業開始**: 着手時に `in_progress/XXX_issue_name.md` へ移動
3. **完了**: 完了時に `completed/NNN_issue_name.md` へ移動（連番付与）

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
- 1つの Issue につき 1つのマークダウンファイルを作成
- ファイル名は `[issue_name].md` の形式（スネークケース推奨）

### ステータス管理
- 🔴 **未着手**: Issue が提起されたが作業開始していない
- 🟡 **提案中**: 設計・調査中
- 🟢 **進行中**: 実装作業中
- ✅ **完了**: 実装・テスト・ドキュメント化が完了

### 優先度
- **高**: 重大な問題、ブロッカー
- **中**: 重要だが緊急ではない
- **低**: 改善提案、将来的な機能

---

## 📝 Issue の更新

Issue の進捗があった場合は、該当ファイルを更新し、このREADME.mdの一覧も更新してください。

---

最終更新: 2025-11-15
