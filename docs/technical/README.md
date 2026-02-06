# Technical Documentation

## 目的

このディレクトリは、repom の**内部実装の判断基準と制約**を記録します。将来、AI エージェントが機能改善や拡張を行う際の参考資料として使用されます。

## 特徴

- ✅ 設計判断の背景
- ✅ 制約と制限事項
- ✅ 代替案とトレードオフ
- ✅ 技術調査と実現可能性の検証
- ✅ 将来の改善時の参考資料

## 命名規則

`<feature_name>_technical.md` または `<topic_name>.md`

## 対象読者

- **repom を改善・拡張する AI エージェント**（主要な対象）
- 内部実装の設計判断を理解したい開発者

## 他のディレクトリとの違い

### `guides/` との違い

- **guides/**: 使い方マニュアル（簡潔、実用的、他の AI エージェントへの教育用）
- **technical/**: なぜそうなっているか（詳細、設計判断、将来の改善時の参考）

**使い分けの例**:
```
guides/base_model_auto_guide.md
→ 「get_response_schema() の使い方」

technical/get_response_schema_technical.md
→ 「なぜこの実装にしたか、制約は何か、代替案は何だったか」
```

### `ideas/` との違い

- **ideas/**: アイデア段階の提案（問題提起）
- **technical/**: 実装済み機能の技術詳細（記録）

## ドキュメントの種類

### 実装判断記録

実装時になぜその方法を選んだか、どのような制約があったかを記録。

**例**: `get_response_schema_technical.md`
- Pydantic の前方参照解決の仕組み
- なぜ forward_refs パラメータが必要か
- 標準型の自動解決の実装理由

### 制約と制限事項

技術的な制約や、理想的ではないが現実的な選択をした理由を記録。

**例**: `alembic_version_locations_limitation.md`
- Alembic の version_locations の制約
- なぜ alembic.ini でしか設定できないか
- 試した代替案とその結果

### AI コンテキスト管理

AI エージェントがドキュメントを効率的に利用するための設計指針。

**例**: `ai_context_management.md`
- ドキュメント構造の設計方針
- トークン消費量の最適化戦略
- 複数エージェント間での情報共有方法

## ドキュメント作成ガイドライン

### 含めるべき内容

✅ 設計判断の理由  
✅ 技術的な制約  
✅ 試した代替案とその結果  
✅ 将来の改善のヒント  
✅ 関連する Issue や Research ドキュメントへのリンク

### 含めるべきでない内容

❌ 基本的な使い方（guides/ に記載）  
❌ アイデア段階の提案（ideas/ に記載）  
❌ 実装タスクの追跡（issue/ に記載）

## ライフサイクル

```
ideas/              → アイデア提案
    ↓
technical/          → 技術調査・設計判断（必要に応じて）
    ↓
issue/active/       → 実装計画
    ↓
issue/completed/    → 実装完了
    ↓
technical/          → 実装判断の記録（参考資料として更新・追記）
```

## 現在のドキュメント

### get_response_schema_technical.md
Pydantic スキーマ生成の技術詳細と前方参照解決の実装判断。

### alembic_version_locations_limitation.md
Alembic の version_locations 設定の制約と、なぜ alembic.ini でしか設定できないかの説明。

### ai_context_management.md
AI エージェントがドキュメントを効率的に利用するための設計指針とトークン最適化戦略。

### hybrid_package_logging_strategy.md
ハイブリッドパッケージにおけるロギング戦略の技術詳細。

### auto_forward_refs_resolution.md
Pydantic モデルの前方参照（Forward References）自動解決の調査と実装案。

---

## 使い方（AI エージェント向け）

### 機能改善時

1. 該当機能の technical ドキュメントを読む
2. 過去の設計判断と制約を理解する
3. 改善案を検討し、必要に応じて technical/ に追記

### 新機能実装時

1. 実装完了後、technical/ にドキュメント作成
2. 設計判断の理由を記録
3. 将来の改善ポイントがあれば同じドキュメントに記載

---

最終更新: 2026-01-20
