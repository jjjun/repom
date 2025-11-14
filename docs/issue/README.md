# Issue Tracker - repom

このディレクトリは、repom プロジェクトの改善提案と課題管理のためのドキュメントを格納します。

## 📋 現在の Issue 一覧

### Issue #1: get_response_schema() の前方参照改善

**ファイル**: `get_response_schema_forward_refs_improvement.md`

**ステータス**: ✅ Phase 1 & 2 完了（2025-11-14）

**概要**:
`BaseModel.get_response_schema()` メソッドの前方参照解決を改善し、標準型（List, Dict, Optional 等）を自動的に含め、エラーメッセージを改善。

**優先度**: 高

**実装内容**:
- ✅ Phase 1: 標準型の自動追加（完了）
- ✅ Phase 2: エラーメッセージの改善 + 未解決型の自動検出（完了）
- ⏭️ Phase 3: ドキュメント改善（オプション）
- 🔬 将来: 完全自動依存解決（調査中 - `docs/research/`）

**テスト結果**:
- 31/31 テスト全てパス
- 既存テスト（27）+ Phase 1 改善効果テスト（3）+ Phase 2 テスト（4）

**関連ファイル**:
- `repom/base_model.py` - 実装ファイル（**Phase 1 & 2 実装済み**）
- `tests/unit_tests/test_response_field.py` - 基本テスト（13テスト）
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
