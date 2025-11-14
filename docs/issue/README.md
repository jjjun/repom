# Issue Tracker - repom

このディレクトリは、repom プロジェクトの改善提案と課題管理のためのドキュメントを格納します。

## � ディレクトリ構造

```
docs/issue/
├── README.md              # このファイル（Issue 管理インデックス）
├── completed/             # 完了・解決済み Issue
│   └── 001_*.md          # Issue #1（完了）
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

## 🚧 作業中の Issue

*現在作業中の Issue はありません*

## 📝 Backlog

*現在計画中の Issue はありません*

---

## 新しい Issue の作成

新しい Issue を作成する際は:

1. **Backlog 段階**: `backlog/XXX_issue_name.md` にファイル作成
2. **作業開始**: 着手時に `in_progress/XXX_issue_name.md` へ移動
3. **完了**: 完了時に `completed/XXX_issue_name.md` へ移動

完了済み Issue には連番（001, 002, 003...）を付与してください。

---

*最終更新: 2025-11-14*
- `tests/unit_tests/test_response_schema_forward_refs.py` - 前方参照テスト（**31テスト**）
- `tests/unit_tests/test_response_schema_fastapi.py` - FastAPI統合テスト（9テスト）
- `docs/get_response_schema_technical.md` - 技術ドキュメント
- `docs/get_response_schema_testing_guide.md` - テストガイド
- `docs/research/auto_forward_refs_resolution.md` - 将来の自動依存解決の調査

**完了したステップ**:
1. ✅ テスト戦略の確立
2. ✅ 包括的なテストの作成（27テスト）
3. ✅ ドキュメント化
4. ✅ Phase 1 改善提案の実装（標準型の自動解決）
5. ✅ 改善効果の検証（3テスト追加）
6. ✅ Phase 2 改善提案の実装（エラーメッセージ + 未解決型検出）
7. ✅ Phase 2 テストの追加（4テスト）
8. ✅ README への反映

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

## 📁 ディレクトリ構造

```
docs/
├── issue/
│   ├── README.md                                      # このファイル
│   ├── get_response_schema_forward_refs_improvement.md # Issue #1
│   └── [その他の Issue ドキュメント]
├── get_response_schema_technical.md                   # 技術ドキュメント
├── get_response_schema_testing_guide.md               # テストガイド
└── [その他のドキュメント]
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

最終更新: 2025-11-14
