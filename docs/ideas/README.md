# アイデアディレクトリ

## 概要

このディレクトリには **機能アイデア**と**改善提案**を保存します。ここに記載されるアイデアは、構想段階または計画段階です。

**目的**: アイデア段階の提案を記録（実装前）

**特徴**:
- ✅ 問題提起と動機
- ✅ ユースケース
- ✅ **厳格な文書長制限（250-350行）**
- ❌ 完全な実装コードは含めない

**命名規則**: `<feature_name>.md`

## 📏 ドキュメント作成ガイドライン

### 厳格な制限
- **総行数**: 250-350行まで
- **コード例**: 1例につき5-10行まで
- **アプローチ**: ONE recommended approach のみ

### 含めないもの
❌ 完全な実装コード（すぐ古くなる）  
❌ 複数アプローチの詳細比較（1つに絞る）  
❌ 深い技術実装の詳細（コードや technical/ に移す）  
❌ 冗長なコード例（1概念につき1例まで）  
❌ 「Additional Ideas」セクション（別ファイルに分割）

### 含めるもの
✅ 問題定義とスコープ  
✅ 既存コマンド/機能への影響  
✅ 制約（後方互換性など）  
✅ 検証基準  
✅ コード最小限の概念説明

## 📋 必須テンプレート

**新しい idea ドキュメントを作るときは以下をコピーして使用**:

```markdown
# [Feature Name]

## ステータス
- **段階**: アイディア
- **優先度**: 高/中/低
- **複雑度**: 高/中/低
- **作成日**: YYYY-MM-DD
- **最終更新**: YYYY-MM-DD

## 概要 (2-3 sentences)
このアイデアの概要を簡潔に説明。

## モチベーション

### 現在の問題 (50-80 lines)
- 何が壊れているか／欠けているか
- 影響するコマンドや機能
- 代表的なエラー例（短く、完全なコードは避ける）

### 理想の動作 (30-50 lines)
- どうあるべきか
- 主要なメリット（箇条書き）
- シンプルな利用例（5行以内）

## ユースケース (60-80 lines)

[3-5 件のユースケース。それぞれに以下を含める]:
- 簡潔な説明（2-3文）
- 最小限のコード例（3-5行）
- 重要な理由

## 推奨アプローチ (50-70 lines)

**ONE approach only**. 以下を含める:
- なぜこのアプローチか
- 主要コンセプト（説明重視、実装コードは避ける）
- トレードオフ
- 統合ポイント

❌ DO NOT include:
- Complete implementations
- Multiple approach comparisons
- Deep technical details

## 統合ポイント (30-50 lines)

- Affected files (list only)
- Existing features impacted
- Backward compatibility considerations

## 次のステップ (40-60 lines)

### 実装優先順位
#### Phase 1: 基本機能（高優先度）
- [ ] Implementation tasks

#### Phase 2: 統合とドキュメント（中優先度）
- [ ] Integration tasks

#### Phase 3: 高度な機能（低優先度）
- [ ] Advanced features

### 検証項目
- [ ] Validation checklist

### 実装決定事項
1. Decision 1
2. Decision 2

## 解決すべき質問 (20-40 lines)

- Key decisions needed
- Open questions
- Risks to consider

## 関連ドキュメント (10-20 lines)

- Links to related files
```

**TOTAL TARGET**: 250-350 lines

## 💡 AI エージェント向け Tips

idea ドキュメント作成時の注意点:

1. **まずアウトライン** → 構成を先に提示して承認を得る
2. **スコープ確認** → 詳細版か簡潔版かを確認
3. **段階的に作成** → セクションごとにフィードバックを得る
4. **行数チェック** → 最後に行数を報告
5. **簡潔に** → 実装コードより説明を優先

### Red Flags 🚩
次の場合は停止して確認:
- 完全な実装コードを書いている
- 3つ以上のアプローチを詳細比較している
- 10行以上のコード例がある
- 類似コードが繰り返されている

## アイデアのライフサイクル

```
docs/ideas/         → Initial concept and exploration
    ↓
docs/issue/active/  → Concrete implementation plan
    ↓
docs/issue/completed/ → Implementation complete
```

## 🎯 ユーザー向け指示テンプレート

AI にアイデアドキュメントを依頼する場合:

```
docs/ideas/README.md のテンプレートに従ってアイデアドキュメントを作成してください。

要件:
- テンプレート構造を厳密に遵守
- 総行数は 350 行以内
- 実装コードではなく概念説明を重視
- ONE recommended approach のみ

[Attach: docs/ideas/README.md]
```

## 現在のアイデア

### 1. Schema Validation Command
**File**: `schema_validation_command.md`
**目的**: デプロイ前に全モデルのスキーマを検証する CLI コマンド
**優先度**: 中
**ステータス**: アイデア段階

### 2. Schema File Generation
**File**: `schema_file_generation.md`
**目的**: Pydantic スキーマを JSON Schema に出力して API ドキュメント化
**優先度**: 低
**ステータス**: アイデア段階

### 3. API Type Resolution
**File**: `api_type_resolution.md`
**目的**: FastAPI/Flask の response_model 型解決を自動化
**優先度**: 低
**ステータス**: アイデア段階

## アイデア投稿

### プロジェクト参加者向け
1. `docs/ideas/` に新規 markdown を作成（テンプレート使用）
2. 分かりやすいファイル名にする（例: `caching_layer_implementation.md`）
3. 各セクションを可能な限り埋める
4. 関連 Issue があればリンクする
5. コミットメッセージ: `docs(ideas): Add [idea title]`

### 外部コントリビューター向け
1. GitHub Discussions の「Ideas」カテゴリで提案
2. 投稿にテンプレートを使用
3. 適切と判断された場合、管理者が `docs/ideas/` に反映

## アイデア評価基準

評価時の観点:
- **価値**: ユーザーの実問題を解決するか
- **スコープ**: このプロジェクトの目的（共通基盤）と整合するか
- **複雑度**: 実装コストに見合うか
- **互換性**: 後方互換性を保てるか
- **保守性**: 長期運用可能か

## 次のステップ

### 実装フェーズへ
実装に進められる段階になったら:
1. `docs/issue/active/XXX_[idea_name].md` を作成
2. ステータスを「Planning」または「Ready for Implementation」に更新

## アーカイブ

不要になったアイデアや代替済みのアイデアは、ドキュメント内のステータス更新でアーカイブ扱いとする。

## 質問

アイデア運用に関する質問は以下を参照:
- `docs/issue/README.md` - Issue 管理フロー
- GitHub Discussions のプロジェクト管理者
