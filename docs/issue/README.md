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

## 🚧 作業中の Issue

現在作業中の Issue はありません。

---

## 📝 実装予定・作業中の Issue

### Issue #7: Annotation Inheritance の実装検証

**ファイル**: `active/007_annotation_inheritance_validation.md`

**ステータス**: 📝 調査待機中（2025-11-15）

**概要**:
Issue #006 (Phase 1.1) で BaseModel の `__annotations__` 継承問題を修正したが、この実装が正しいのか、他への影響がないかを調査する必要がある。

**調査項目**:
1. Python の `__annotations__` 継承動作の確認
2. SQLAlchemy 2.0 の推奨パターンとの整合性
3. 他のフレームワークとの互換性（FastAPI, Pydantic）
4. エッジケースの検証（多重継承, Mixin）
5. パフォーマンスへの影響
6. 代替実装の検討

**関連 Issue**: #006 (SQLAlchemy 2.0 migration)

**影響範囲**:
- repom 内部: BaseModel, サンプルモデル, テストコード
- 外部プロジェクト: repom を使用するすべてのプロジェクト

**技術的決定事項**:
- `Column()` → `mapped_column()` + `Mapped[]` 型ヒント
- relationship には文字列で前方参照（循環参照回避）
- 後方互換性を維持し、段階的移行
- 移行ガイド提供（外部プロジェクト向け）

---

## 📋 完了済み Issue

### Issue #1: get_response_schema() の前方参照改善

**ファイル**: `completed/001_get_response_schema_forward_refs_improvement.md`

**ステータス**: ✅ 完了（2025-11-14）

**概要**:
`BaseModel.get_response_schema()` メソッドの前方参照解決改善。Phase 1（標準型の自動解決）と Phase 2（エラーメッセージ改善 + 環境別エラーハンドリング）を実装。

**結果**:
- Phase 1: 標準型（List, Dict, Optional 等）の自動解決
- Phase 2: 未定義型の自動検出とエラーメッセージ改善
- テスト: 31/31 パス（Phase 1: 3テスト + Phase 2: 4テスト）
- ドキュメント: 詳細な README セクション + research ディレクトリ

**関連ドキュメント**:
- 調査: `docs/research/auto_forward_refs_resolution.md`
- 実装: メイン `README.md` の Phase 1 & 2 セクション参照
- 技術詳細: `docs/technical/get_response_schema_technical.md`

---

### Issue #2: SQLAlchemy カラム継承制約による use_id 設計の課題

**ファイル**: `completed/002_sqlalchemy_column_inheritance_constraint.md`

**ステータス**: ✅ 完了（2025-11-14）

**概要**:
`BaseModel` と `BaseModelAuto` で `use_id` パラメータのデフォルト値を制御する際、SQLAlchemy のカラム継承制約により複合主キーモデルで `id` カラムが意図せず継承される問題を解決。

**結果**:
- 抽象クラス（`__tablename__` なし）にはカラムを追加しない仕様
- 具象クラスのみに `use_id` に基づいて `id` カラムを追加
- `BaseModel` と `BaseModelAuto` の両方でデフォルト `use_id=True` を維持
- 複合主キーモデルで `use_id=False` を明示的に指定すれば `id` カラムなし
- テスト: 全 103 テスト合格

**関連ドキュメント**:
- 実装: `repom/base_model.py` と `repom/base_model_auto.py`
- テスト: `tests/unit_tests/test_model_no_id.py`

---

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
  - `docs/guides/base_model_auto_guide.md` 作成（400行）
  - `docs/guides/repository_and_utilities_guide.md` 作成（400行）
  - `README.md` 簡略化（1,388行→291行）
  - `.github/copilot-instructions.md` 更新
  - `docs/technical/ai_context_management.md` 作成
- Phase 7: 外部プロジェクトへの移行通知（未実施）

**ドキュメント成果物**:
- 2つの詳細ガイド（base_model_auto_guide.md, repository_and_utilities_guide.md）
- AI エージェントが効率的に参照できる構造
- トークン消費量の最適化（9%で全ガイド同時アクセス可能）

**関連ドキュメント**:
- 実装ガイド: `docs/guides/base_model_auto_guide.md`
- リポジトリガイド: `docs/guides/repository_and_utilities_guide.md`
- 技術詳細: `docs/technical/get_response_schema_technical.md`
- AI コンテキスト管理: `docs/technical/ai_context_management.md`

---

### Issue #5: 柔軟な auto_import_models 設定

**ファイル**: `completed/005_flexible_auto_import_models.md`

**ステータス**: ✅ 完了（2025-11-15）

**概要**:
設定ファイルで複数のモデルディレクトリを指定できる機能を実装。`models/__init__.py` への手動記述を不要にし、Alembic マイグレーションと db コマンドでのモデル認識ミスを防ぐ。

**実装内容**:
- Phase 1: 基本機能 ✅
  - `auto_import_models_by_package()` 関数（セキュリティ検証付き）
  - `auto_import_models_from_list()` 関数（バッチインポート）
  - `MineDbConfig` プロパティ（model_locations, model_excluded_dirs, allowed_package_prefixes）
  - `load_models()` 修正（設定ベース対応）
  - 27個の単体テスト（すべて成功）
  - ガイドドキュメント作成

- Phase 1.5: 設定制御機能 ✅
  - `model_import_strict` プロパティ追加（デフォルト False = 警告のみ）
  - `load_models()` での `fail_on_error` パラメータ連携
  - 4個の単体テスト追加（合計31テスト）
  - ドキュメント更新

**技術的決定事項**:
- Python コード（CONFIG_HOOK 経由）のみサポート
- デフォルトで警告のみ（`model_import_strict=False`）
- セキュリティ検証（`allowed_package_prefixes`、デフォルト `{'repom.'}`）
- セキュリティスキップは直接呼び出しのみ許可
- 後方互換性を維持（`model_locations=None` で従来通り）

**テストカバレッジ**:
- 合計31テスト（セキュリティ6、パッケージインポート8、Config8、統合3、エラーハンドリング3、実世界3、Strict3）
- すべてのテストが成功

**関連ドキュメント**:
- 使用ガイド: `docs/guides/auto_import_models_guide.md`
- 元のアイディア: `docs/ideas/flexible_auto_import_models.md`（280行に削減）

---

### Issue #6: SQLAlchemy 2.0 スタイルへの移行

**ファイル**: `completed/006_migrate_to_sqlalchemy_2_0_style.md`

**ステータス**: ✅ 完了（2025-11-15）

**概要**:
repom プロジェクト全体を SQLAlchemy 2.0 の推奨スタイル（`Mapped[]` 型ヒント + `mapped_column()`）に移行。型安全性の向上、エディタ補完の改善、将来のバージョン互換性を確保。

**実装内容**:
- Phase 1: repom コア移行 ✅
  - BaseModel migration (Commit: 964504d)
  - Sample models migration (Commit: ae71332)
  - AutoDateTime docstring (Commit: a65f6fe)
  - BaseModelAuto docstring (Commit: c7d787a)
  
- Phase 2: テストコード移行 ✅
  - 17テストファイル、115+ Column() 定義を移行
  - test_forward_refs_generic_list_response_pattern 修正 (Commit: 92f50d1)
  - Commits: 87b5fb8, d56f382, cbef52e, 92f50d1
  
- Phase 3: ドキュメント整備 ✅
  - guides, README, copilot-instructions 更新
  - Commits: 168b70a, 1379ac0

**テスト結果**:
- 186/186 unit tests passing (1 skipped - FastAPI)
- 本番環境テスト完了、問題なし

**技術的成果**:
- Annotation inheritance バグの発見と修正
- AutoDateTime 設計仕様の明確化
- 動的カラム追加と型ヒントの統合手法確立

**関連コミット**: 964504d, ae71332, a65f6fe, c7d787a, 87b5fb8, d56f382, cbef52e, 92f50d1, 168b70a, 1379ac0

---

### Issue #8: Alembic マイグレーションファイルの保存場所制御

**ファイル**: `completed/008_alembic_migration_path_conflict.md`

**ステータス**: ✅ 完了（2025-11-16）

**概要**:
外部プロジェクトで repom を使用する際、マイグレーションファイルの保存場所を制御できない問題を解決。Alembic の制約により `alembic.ini` の `version_locations` を唯一の設定源とする実装に変更。

**最終的な解決策**:
- `alembic.ini` に `version_locations` を明示的に記述
- ファイル作成と実行の両方で同じ設定を使用
- `MineDbConfig._alembic_versions_path` を削除（env.py での動的設定は効かないため）

**実装変更**:
- `config.py`: `_alembic_versions_path` フィールドを完全削除
- `alembic/env.py`: `version_locations` の動的設定を削除
- `alembic.ini`: `version_locations = alembic/versions` を追加
- テスト: `test_alembic_config.py` を削除（機能が存在しなくなったため）

**外部プロジェクト設定**:
```ini
# mine-py/alembic.ini
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

**関連ドキュメント**:
- 技術調査: `docs/technical/alembic_version_locations_limitation.md`
- ユーザーガイド: `README.md#alembic-マイグレーション`
- 開発者ガイド: `AGENTS.md#alembic-configuration`

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

最終更新: 2025-11-16
