# repom Guides

repom の使い方を機能別に整理したガイド集です。

## 🧭 概要

**目的**: 他の AI エージェントや開発者に機能を教えるための実用的なマニュアル

**特徴**:
- ✅ 簡潔（How-to 重視）
- ✅ コード例が豊富
- ✅ すぐに使える情報
- ✅ 初心者にも分かりやすい

**命名規則**: `<feature_name>_guide.md`

**例**:
```
base_model_auto_guide.md          # Pydantic スキーマ自動生成
repository_and_utilities_guide.md # Repository パターン
testing_guide.md                  # テスト戦略
```

**対象読者**:
- 開発者（機能の使い方を学ぶ）
- AI エージェント（実装時の参考）

**テンプレート**:
```markdown
# [Feature Name] Guide

## 概要
[機能の説明]

## 基本的な使い方
[コード例]

## 高度な使い方
[応用例]

## トラブルシューティング
[よくある問題と解決方法]

## 関連ドキュメント
[リンク]
```

## 📂 ガイドカテゴリ

### 🎨 [model/](model/) - モデル定義
- BaseModelAuto による Pydantic スキーマ自動生成
- システムカラムとカスタム型
- 論理削除（ソフトデリート）

### 📦 [repository/](repository/) - リポジトリパターン
- BaseRepository / AsyncBaseRepository の使い方
- 検索・クエリ・フィルタリング
- セッション管理パターン
- SoftDelete 機能

### ⚡ [features/](features/) - 機能別ガイド
- モデルの自動インポート
- マスターデータ同期
- ロギング

### 🐘 [postgresql/](postgresql/) - PostgreSQL
- Docker による PostgreSQL セットアップ
- 環境別データベース構成
- 接続情報とトラブルシューティング

### 🧪 [testing/](testing/) - テスト
- Transaction Rollback パターン
- テストフィクスチャの使い方
